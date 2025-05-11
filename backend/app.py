import redis
from sentence_transformers import SentenceTransformer
import os
import time
from typing import List, Dict, Any
from agent import summarize_document  # Assuming summarize_document is synchronous or handled appropriately
import git
import shutil
import asyncio
import socket
import json
import threading  # Changed from 'thread' to 'threading'

# Watchdog imports for file system monitoring
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, LoggingEventHandler  # LoggingEventHandler is optional for debug

os.environ["TOKENIZERS_PARALLELISM"] = "false"
# 1. Configure Redis Connection
REDIS_HOST = "localhost"  # Or your Redis instance's hostname
REDIS_PORT = 6379  # Default Redis port
REDIS_PASSWORD = None  # Or your Redis password, if any
VECTOR_SET_NAME = "file_embeddings_set"  # Name for your Redis Vector Set


def get_redis_connection():
    """Establishes and returns a Redis connection."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                        decode_responses=True)
        r.ping()
        print("Successfully connected to Redis!")
        return r
    except redis.exceptions.ConnectionError as e:
        print(f"Error connecting to Redis: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while connecting to Redis: {e}")
        return None


# 2. Load Embedding Model
def load_embedding_model(model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
    """Loads a Sentence Transformer model for generating embeddings."""
    try:
        model = SentenceTransformer(model_name)
        print(f"Successfully loaded model: {model_name}")
        return model
    except Exception as e:
        print(f"Error loading the embedding model: {e}")
        return None


# 3.  Metadata Extraction and Embedding Generation
async def process_file_and_get_data(
        abs_file_path: str,
        relative_file_path: str,
        model: SentenceTransformer,
        commit_hash: str
) -> Dict[str, Any]:
    """
    Extracts metadata from a text file, generates an embedding,
    and returns the data as a dictionary.
    Includes commit_hash and uses relative_file_path for identification.
    """
    try:
        if not os.path.exists(abs_file_path) or not os.path.isfile(abs_file_path):
            print(f"[WARN] File {abs_file_path} not found or not a file during processing. Skipping.")
            return {}

        file_name = os.path.basename(abs_file_path)
        file_size = os.path.getsize(abs_file_path)

        content_read = False
        file_content = b""  # Initialize file_content
        for _ in range(3):
            try:
                with open(abs_file_path, 'rb') as f:
                    file_content = f.read()
                content_read = True
                break
            except PermissionError:
                print(f"[WARN] Permission denied reading {abs_file_path}. Retrying in 0.1s...")
                await asyncio.sleep(0.1)  # Use asyncio.sleep in async function
            except FileNotFoundError:
                print(f"[WARN] File {abs_file_path} disappeared before reading. Skipping.")
                return {}

        if not content_read:
            print(f"[ERROR] Could not read file content from {abs_file_path} after retries. Skipping.")
            return {}

        if not file_content.strip():
            print(f"[INFO] File {abs_file_path} is empty. Skipping embedding.")
            return {}

        # Assuming summarize_document can be called from an async context
        # If summarize_document is purely synchronous CPU-bound, it might block the event loop
        # Consider running it in an executor if it's blocking: loop.run_in_executor(None, summarize_document, abs_file_path)
        summary = await summarize_document(abs_file_path)
        print(summary)
        embedding = model.encode(summary).tolist()

        metadata = {
            "file_name": file_name,
            "file_size": file_size,
            "relative_file_path": relative_file_path,
            "commit_hash": commit_hash,
            "embedding": embedding,
            "content_summary": summary
        }
        return metadata
    except FileNotFoundError:
        print(f"[WARN] File {abs_file_path} was not found during metadata extraction (possibly deleted). Skipping.")
        return {}
    except Exception as e:
        print(f"Error processing file {abs_file_path}: {e}")
        return {}


# 4. Store Data in Redis Vector Sets
def store_in_redis(redis_client: redis.Redis, data: Dict[str, Any], vector_set_name: str) -> bool:
    if not redis_client:
        print("Redis client is not initialized.")
        return False
    if not data or "embedding" not in data:
        print("No data or embedding provided to store.")
        return False

    try:
        record_id = f"{data['relative_file_path']}:{data['commit_hash']}"
        print(f"[INFO] Storing file {record_id} in Redis.")
        vector = data["embedding"]
        attributes = {}
        for k, v_item in data.items():
            if k != "embedding":
                if isinstance(v_item, (list, dict)):
                    attributes[k] = str(v_item)
                else:
                    attributes[k] = v_item

        # Using a pipeline for atomicity if hset and vadd should ideally be atomic
        pipe = redis_client.pipeline()
        pipe.hset(record_id, mapping=attributes)
        pipe.vset().vadd(vector_set_name, vector, record_id)  # Ensure your redis-py version supports vset in pipeline
        pipe.execute()

        print(f"Successfully stored data for record: {record_id}")
        return True
    except redis.exceptions.ResponseError as e:
        print(
            f"Redis command error storing data for {data.get('relative_file_path', 'N/A')}:{data.get('commit_hash', 'N/A')}: {e}")
        print("Ensure the Redis Stack 'Vector Search' module is loaded.")
        return False
    except Exception as e:
        print(
            f"Error storing data in Redis for {data.get('relative_file_path', 'N/A')}:{data.get('commit_hash', 'N/A')}: {e}")
        return False


class ChangeHandler(FileSystemEventHandler):
    """Handles file system events and triggers App actions. Now includes threaded socket listener."""

    def __init__(self, app_instance, watch_path, redis_client, embedding_model, repo):
        super().__init__()
        self.app = app_instance  # app_instance is an instance of App class
        self.watch_path = os.path.abspath(watch_path)
        self.git_dir_to_ignore = os.path.join(self.watch_path, '.git')
        self.redis_client = redis_client
        self.embedding_model = embedding_model

        # Start the socket listening in a separate thread
        self.socket_thread = threading.Thread(target=self.listen_socket, daemon=True)
        self.socket_thread.start()
        self.repo = repo

    def listen_socket(self):
        """Listens for incoming socket connections in a dedicated thread."""
        host = "127.0.0.1"
        port = 30717
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
            try:
                s.bind((host, port))
                s.listen()
                print(f"[NETWORK_THREAD] Socket server listening on {host}:{port}")
            except Exception as e:
                print(f"[NETWORK_THREAD][ERROR] Could not start socket server: {e}")
                return

            while True:  # Keep accepting new connections
                try:
                    conn, addr = s.accept()
                    with conn:
                        print(f"[NETWORK_THREAD] Connected by {addr}")
                        while True:  # Handle persistent connection
                            data = conn.recv(10000)
                            if not data:
                                print(f"[NETWORK_THREAD] Connection closed by {addr}")
                                break  # Break from inner loop to wait for a new connection
                            # Process received data
                            self.handle_network_request(conn, data)
                except socket.error as e:
                    print(f"[NETWORK_THREAD][ERROR] Socket error during accept/recv: {e}")
                    # Depending on error, might want to break outer loop or continue
                except Exception as e:
                    print(f"[NETWORK_THREAD][ERROR] Unexpected error in listen_socket: {e}")
                    break  # Exit listen_socket on unexpected errors

    def handle_network_request(self, conn: socket.socket, data: bytes):
        """Handles incoming data from a socket connection. Runs in the socket_thread."""
        # Assuming analyze_search_query is an async function defined in searcher.py
        # You need to import it if it's not already available in this scope
        try:
            from searcher import analyze_search_query  # Ensure this import is valid
        except ImportError:
            print("[NETWORK_THREAD][ERROR] Could not import analyze_search_query from searcher.")
            try:
                conn.sendall(json.dumps({"error": "Internal server configuration error"}).encode('utf-8'))
            except Exception as e:
                print(f"[NETWORK_THREAD][ERROR] Failed to send import error to client: {e}")
            return

        print("[NETWORK_THREAD][INFO] Analyzing search query")
        try:
            query_text = data.decode('utf-8')
            # Call the async function analyze_search_query using asyncio.run()
            # This creates a new event loop for each call, which is simple but might have overhead if called very frequently.
            result_from_analysis = asyncio.run(analyze_search_query(query_text))

            if result_from_analysis:
                print("[NETWORK_THREAD][INFO] Performing Redis vector similarity search")
                embedding = self.embedding_model.encode(result_from_analysis).tolist()
                # Ensure redis_client is initialized with decode_responses=True for string keys
                redis_search_res = self.redis_client.vset().vsim(VECTOR_SET_NAME, embedding, True, 3)

                print("[NETWORK_THREAD] Sending results")
                for key, value in redis_search_res.items():
                    if value >= 0.75:
                        commit_hash = key.split(':')[1]
                        file_path = key.split(':')[0]
                        self.repo.git.checkout(commit_hash, '--', file_path)
                        conn.sendall(file_path.encode('utf-8'))
            else:
                print("[NETWORK_THREAD][INFO] Search query analysis returned no actionable result.")
                # Optionally send a message indicating no results from analysis
                conn.sendall(
                    json.dumps({"message": "Query processed, no specific results from analysis"}).encode('utf-8'))

        except UnicodeDecodeError:
            print("[NETWORK_THREAD][ERROR] Could not decode query from client (expected UTF-8).")
            try:
                conn.sendall(json.dumps({"error": "Invalid query encoding, expected UTF-8"}).encode('utf-8'))
            except Exception as e:
                print(f"[NETWORK_THREAD][ERROR] Failed to send decode error to client: {e}")
        except RuntimeError as e:
            # This can happen if asyncio.run() is called in a context where it's not allowed (e.g. an already running loop in the same thread)
            # However, since this thread is separate and dedicated to socket ops, it should usually be fine.
            print(f"[NETWORK_THREAD][ERROR] Runtime error calling async function: {e}")
            try:
                conn.sendall(json.dumps({"error": "Internal server error processing query"}).encode('utf-8'))
            except Exception as send_e:
                print(f"[NETWORK_THREAD][ERROR] Failed to send runtime error to client: {send_e}")
        except Exception as e:
            print(f"[NETWORK_THREAD][ERROR] Error in handle_network_request: {e}")
            try:
                # Attempt to send a generic error response
                error_response = json.dumps({"error": "Failed to process request due to an internal error."})
                conn.sendall(error_response.encode('utf-8'))
            except Exception as send_e:
                print(f"[NETWORK_THREAD][ERROR] Failed to send error message to client: {send_e}")

    def _should_process(self, event_path):
        abs_event_path = os.path.abspath(event_path)
        filename = os.path.basename(abs_event_path)

        if abs_event_path.startswith(self.git_dir_to_ignore + os.sep) or abs_event_path == self.git_dir_to_ignore:
            return False
        if filename == ".DS_Store" or \
                filename.endswith((".swp", ".swx", "~", ".tmp", ".TMP", ".part", ".crdownload", ".sage~")) or \
                filename.startswith(("~", ".~", "._", "NFS")):
            return False
        if not filename.endswith(".docx"):
            return False
        return True

    def _handle_event(self, event_path, event_type):
        if not self._should_process(event_path):
            return

        print(f"[WATCHDOG] Detected {event_type}: {event_path}")
        try:
            # Ensure self.app.path is defined (should be by App.init_directory)
            if not self.app.path:
                print("[WARN_WATCHDOG] App path not set. Skipping git operation.")
                return

            if os.path.commonpath([self.app.path, os.path.abspath(event_path)]) != self.app.path:
                print(
                    f"[WARN_WATCHDOG] Event path {event_path} is outside the repository path {self.app.path}. Skipping.")
                return
            relative_path = os.path.relpath(event_path, self.app.path)
        except ValueError:
            print(
                f"[WARN_WATCHDOG] Could not determine relative path for {event_path} against {self.app.path}. Skipping.")
            return
        except Exception as e:
            print(f"[ERROR_WATCHDOG] Error determining relative path: {e}")
            return

        # Watchdog events are handled in their own threads, so calling asyncio.run here is okay.
        res = asyncio.run(self.app.git_add(filepaths=relative_path))
        if res == 1:
            print("[INFO] creating a new commit")
            commit_message = f"Auto-commit: {event_type} on {relative_path}"
            asyncio.run(self.app.git_commit(commit_message))
        else:
            print("[INFO] not enought changes to create commit")

    def on_created(self, event):
        super().on_created(event)
        if not event.is_directory:
            self._handle_event(event.src_path, "created")

    def on_modified(self, event):
        super().on_modified(event)
        if not event.is_directory:
            if os.path.exists(event.src_path):
                self._handle_event(event.src_path, "modified")

    def on_deleted(self, event):
        super().on_deleted(event)
        if not event.is_directory:
            self._handle_event(event.src_path, "deleted")

    def on_moved(self, event):
        super().on_moved(event)
        if not event.is_directory:
            print(f"[WATCHDOG] Detected moved: {event.src_path} to {event.dest_path}")
            rel_src_path = None
            rel_dest_path = None

            try:
                if self.app.path and os.path.commonpath(
                        [self.app.path, os.path.abspath(event.src_path)]) == self.app.path:
                    rel_src_path = os.path.relpath(event.src_path, self.app.path)
                if self.app.path and os.path.commonpath(
                        [self.app.path, os.path.abspath(event.dest_path)]) == self.app.path:
                    rel_dest_path = os.path.relpath(event.dest_path, self.app.path)
            except Exception as e:
                print(f"[ERROR_WATCHDOG] Error getting relative paths for move: {e}")
                return

            actions_to_commit = []
            if self._should_process(event.src_path) and rel_src_path:
                res = asyncio.run(self.app.git_add(filepaths=rel_src_path))
                if res == 1:
                    actions_to_commit.append(f"deleted old {rel_src_path}")

            if self._should_process(event.dest_path) and rel_dest_path:
                res = asyncio.run(self.app.git_add(filepaths=rel_dest_path))
                if res == 1:
                    actions_to_commit.append(f"created new {rel_dest_path}")

            if actions_to_commit:
                commit_message = f"Auto-commit: moved/renamed - {' and '.join(actions_to_commit)}"
                asyncio.run(self.app.git_commit(commit_message))


class App():
    def __init__(self):
        self.path = None
        self.repo = None
        print("[INFO] Initializing App: Connecting to Redis and loading embedding model...")
        self.redis_client = get_redis_connection()
        self.embedding_model = load_embedding_model()
        self.observer = None

        if not self.redis_client:
            print("[CRITICAL] Failed to connect to Redis. Embedding storage will not work.")
        if not self.embedding_model:
            print("[CRITICAL] Failed to load embedding model. Embedding generation will not work.")

    def init_directory(self, path: str):
        self.path = os.path.abspath(path)
        print(f"[INFO] Attempting Git initialization for directory: {self.path}")
        self.git_init()
        if self.repo:
            print(
                f"[INFO] Git repository is ready at {self.path}. Monitoring for file changes will use this repository.")
        else:
            print(
                f"[INFO] Git initialization failed or was skipped for '{self.path}'. Monitoring may not work as expected.")

    def git_init(self):
        try:
            if not os.path.isdir(self.path):
                print(f"[ERROR] Path '{self.path}' is not an existing directory. Cannot initialize Git repo.")
                self.repo = None
                return
            try:
                self.repo = git.Repo(self.path)
                print(f"[INFO] Found existing Git repository at {self.path}")
            except git.exc.InvalidGitRepositoryError:
                print(f"[INFO] Initializing new Git repository at {self.path}")
                self.repo = git.Repo.init(self.path)
            print(f"[INFO] Repository operations will use {self.path}")
        except git.exc.GitCommandError as e:
            print(f"[ERROR] Failed to initialize/load Git repository at {self.path}: {e}")
            self.repo = None
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred during git_init: {e}")
            self.repo = None

    async def git_add(self, filepaths='.'):
        if not self.repo:
            print("[ERROR] Repository not initialized. Cannot add files.")
            return
        try:
            # Ensure filepaths are relative to self.path if they are absolute
            if isinstance(filepaths, str) and os.path.isabs(filepaths):
                processed_filepaths = os.path.relpath(filepaths, self.path)
            elif isinstance(filepaths, list):
                processed_filepaths = [os.path.relpath(fp, self.path) if os.path.isabs(fp) else fp for fp in filepaths]
            else:
                processed_filepaths = filepaths

            print(f"[INFO] Staging changes for: {processed_filepaths} in {self.path}...")

            # Get the status of files before adding
            if processed_filepaths == '.':
                status_before = self.repo.git.status('--porcelain').splitlines()
            else:
                status_before = []
                for fp in processed_filepaths:
                    try:
                        status = self.repo.git.status('--porcelain', fp).splitlines()
                        status_before.extend(status)
                    except git.exc.GitCommandError:
                        continue

            # Add the files
            if processed_filepaths == '.':  # Add all changes if '.'
                self.repo.git.add(A=True)
            else:  # Add specific file(s)
                self.repo.git.add(processed_filepaths)

            # Check which files were modified

            for status_line in status_before:
                if status_line.startswith(' M'):  # M means modified
                    file_path = status_line[3:].strip()
                    if file_path in processed_filepaths or processed_filepaths == '.':
                        from diff import compare_document_versions

                        # Get the HEAD commit hash
                        head_commit = self.repo.head.commit
                        previous_commit_hash = head_commit.hexsha

                        previous_summary = self.redis_client.hget(f"{file_path}:{previous_commit_hash}",
                                                                  "content_summary")

                        #return await compare_document_versions(file_path, previous_summary)

            print("[INFO] Changes staged.")

            return 1
        except git.exc.GitCommandError as e:
            # Common error: pathspec '...' did not match any files known to git
            # This can happen if a file is created and deleted quickly by an editor
            if "did not match any files" in str(e.stderr).lower():
                print(
                    f"[WARN_GIT_ADD] File(s) {filepaths} not found by Git, possibly temporary or already handled. Error: {e.stderr.strip()}")
            else:
                print(f"[ERROR] Failed to add files to Git index: {e.stderr.strip()}")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred during git_add: {e}")

    async def git_commit(self, message: str):
        if not self.repo:
            print("[DEBUG_COMMIT] Repository not initialized. Cannot commit.")
            return None
        # This method remains async.
        try:
            status = self.repo.git.status('--porcelain').splitlines()
            staged_changes = any(line and line[0] != ' ' and line[0] != '?' for line in status)  # Exclude untracked

            if not staged_changes:
                print("[INFO] No staged changes detected to commit.")
                return None

            print(f"[INFO] Attempting to commit staged changes with message: '{message}'")
            try:
                conf_reader = self.repo.config_reader()
                if not conf_reader.get_value('user', 'name', fallback=None) or \
                        not conf_reader.get_value('user', 'email', fallback=None):
                    print("[ERROR_COMMIT] Git user.name/email not set. Setting to defaults.")
                    with self.repo.config_writer() as cw:
                        cw.set_value("user", "name", "AutoCommitter").release()
                        cw.set_value("user", "email", "autocommitter@example.com").release()
            except Exception as e:  # Catch broader exceptions like configparser.Error
                print(f"[WARN_COMMIT] Could not verify/set git config, attempting commit anyway: {e}")

            new_commit = self.repo.index.commit(message)
            print(f"[INFO] Commit successful. New commit SHA: {new_commit.hexsha}")

            affected_docx_files = []
            if new_commit.parents:
                parent_commit = new_commit.parents[0]
                for diff_item in parent_commit.diff(new_commit):
                    # Check a_path for renames/deletes, b_path for adds/modifies
                    if diff_item.b_path and diff_item.b_path.endswith('.docx') and diff_item.change_type in (
                    'A', 'M', 'R'):
                        affected_docx_files.append(diff_item.b_path)
                    elif diff_item.a_path and diff_item.a_path.endswith('.docx') and diff_item.change_type in (
                    'D', 'R'):
                        # If renamed, b_path is already captured. If deleted, a_path is the one.
                        if diff_item.change_type == 'D' and diff_item.a_path not in affected_docx_files:  # Avoid double for rename
                            # For deletions, we might not process embeddings, but good to know.
                            # Current process_committed_files_embeddings expects files to exist.
                            print(f"[INFO] Detected deletion of .docx: {diff_item.a_path}")
            else:  # Initial commit
                for item in new_commit.tree.traverse():
                    if isinstance(item, git.Blob) and item.path.endswith('.docx'):
                        affected_docx_files.append(item.path)

            unique_affected_docx = list(set(affected_docx_files))
            if unique_affected_docx:
                print(f"[INFO] Processing embeddings for: {unique_affected_docx}")
                await self.process_committed_files_embeddings(new_commit.hexsha, unique_affected_docx)
            else:
                print(f"[INFO] No .docx files added/modified in this commit for embedding.")
            return new_commit.hexsha
        except git.exc.GitCommandError as e:
            print(f"[ERROR] GitCommandError during commit: {e}")
            if e.stdout: print(f"[ERROR_STDOUT] {e.stdout}")
            if e.stderr: print(f"[ERROR_STDERR] {e.stderr}")
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error in git_commit: {e}")
            return None

    async def process_committed_files_embeddings(self, commit_hash: str, relative_file_paths: List[str]):
        if not self.repo or not self.redis_client or not self.embedding_model:
            print("[ERROR] Cannot process embeddings: App components missing.")
            return

        print(f"[INFO] Starting embedding process for specific files from commit {commit_hash}")
        processed_count = 0
        for rel_path in relative_file_paths:
            abs_file_path = os.path.join(self.path, rel_path)
            if not os.path.exists(abs_file_path):
                print(f"[WARN] File {abs_file_path} (from commit) not found on disk. Skipping embedding.")
                continue

            print(f"[INFO] Processing file for embedding: {rel_path}")
            # process_file_and_get_data is async
            file_data = await process_file_and_get_data(
                abs_file_path,
                rel_path,
                self.embedding_model,
                commit_hash
            )
            if file_data:
                store_in_redis(self.redis_client, file_data, VECTOR_SET_NAME)
                processed_count += 1
        print(f"[INFO] Finished processing embeddings for {processed_count} files from commit {commit_hash}.")

    def start_monitoring(self, directory_to_watch: str):
        if not self.repo:  # Ensure repo is initialized if git operations are crucial for monitoring logic
            print("[ERROR] Git repository not initialized. Monitoring might not be fully functional.")
            # Decide if to proceed or return
            # return

        self.event_handler = ChangeHandler(self, directory_to_watch, self.redis_client, self.embedding_model, self.repo)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, directory_to_watch, recursive=True)

        print(f"[INFO] Starting file system monitor for: {directory_to_watch}")
        self.observer.start()
        # Keep the main thread alive for the observer and socket thread
        try:
            while True:
                time.sleep(1)  # Keep main thread alive
        except KeyboardInterrupt:
            print("[INFO] Monitoring stopped by user (KeyboardInterrupt).")
        finally:
            self.stop_monitoring()

    def stop_monitoring(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()  # Wait for observer thread to finish
            print("[INFO] File system monitor shut down.")
        # The socket_thread is a daemon, so it will exit when the main program exits.
        # If explicit cleanup for the socket thread is needed, it would be more complex.


def main():
    app = App()
    if not app.redis_client or not app.embedding_model:
        print("[EXIT] Cannot run example due to missing Redis connection or embedding model.")
        return  # Changed from exit() to return for cleaner exit from main

    user_repo_path = "../../workdir_monitor_test"
    user_repo_path = os.path.abspath(user_repo_path)

    if not os.path.exists(user_repo_path):
        print(f"[SETUP] Test directory {user_repo_path} does not exist. Creating it now.")
        os.makedirs(user_repo_path, exist_ok=True)
        print(f"[SETUP] Created test directory {user_repo_path}. You can now add/modify .docx files in it.")
    else:
        print(f"[SETUP] Using existing test directory: {user_repo_path}")

    app.init_directory(user_repo_path)

    if app.repo:
        print("\n[INFO] Checking for initial uncommitted changes...")
        # asyncio.run returns the result of the coroutine
        add_success = asyncio.run(app.git_add('.'))
        if add_success == 1:  # Check if add operation indicated any processing
            initial_commit_hash = asyncio.run(app.git_commit("Initial commit of existing files upon startup"))
            if initial_commit_hash:
                print(f"Initial commit successful: {initial_commit_hash}")
            else:
                print("No initial staged changes to commit, or commit failed.")
        else:
            print("Initial git add failed or found nothing to add.")

        app.start_monitoring(user_repo_path)  # This will block until KeyboardInterrupt
    else:
        print(f"[ERROR] Repository not initialized at {user_repo_path}. Cannot start monitoring.")

    print("\n--- Script End (if monitoring was not started or was stopped) ---")
    if app.redis_client:
        try:
            app.redis_client.close()
            print("Redis connection closed.")
        except Exception as e:
            print(f"Error closing Redis connection: {e}")


if __name__ == '__main__':
    main()