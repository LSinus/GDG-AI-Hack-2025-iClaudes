import redis
from sentence_transformers import SentenceTransformer
import os
import time
from typing import List, Dict, Any
from agent import summarize_document
import git
import shutil
import asyncio
import socket
import json

# Watchdog imports for file system monitoring
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, LoggingEventHandler  # LoggingEventHandler is optional for debug


os.environ["TOKENIZERS_PARALLELISM"] = "false"
# 1. Configure Redis Connection
REDIS_HOST = "localhost"  # Or your Redis instance's hostname
REDIS_PORT = 6379  # Default Redis port
REDIS_PASSWORD = None  # Or your Redis password, if any
VECTOR_SET_NAME = "file_embeddings"  # Name for your Redis Vector Set


def get_redis_connection():
    """Establishes and returns a Redis connection."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                        decode_responses=True)  # Keep bytes for vectors
        r.ping()  # Check if the connection is successful
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
        # Check if file still exists before processing (it might be a temporary file)
        if not os.path.exists(abs_file_path) or not os.path.isfile(abs_file_path):
            print(f"[WARN] File {abs_file_path} not found or not a file during processing. Skipping.")
            return {}

        file_name = os.path.basename(abs_file_path)
        file_size = os.path.getsize(abs_file_path)

        # Add a small delay and retry for reading, as some editors lock files briefly
        content_read = False
        for _ in range(3):  # Try 3 times
            try:
                with open(abs_file_path, 'rb') as f:
                    file_content = f.read()
                content_read = True
                break
            except PermissionError:
                print(f"[WARN] Permission denied reading {abs_file_path}. Retrying in 0.1s...")
                time.sleep(0.1)
            except FileNotFoundError:
                print(f"[WARN] File {abs_file_path} disappeared before reading. Skipping.")
                return {}

        if not content_read:
            print(f"[ERROR] Could not read file content from {abs_file_path} after retries. Skipping.")
            return {}

        if not file_content.strip():  # If file is empty or only whitespace
            print(f"[INFO] File {abs_file_path} is empty. Skipping embedding.")
            return {}

        summary = await summarize_document(abs_file_path)
        print(summary)
        embedding = model.encode(summary).tolist()

        metadata = {
            "file_name": file_name,
            "file_size": file_size,
            "relative_file_path": relative_file_path,
            "commit_hash": commit_hash,
            "embedding": embedding,
            #"content_summary": file_content[:200]
        }
        return metadata
    except FileNotFoundError:  # Catch if file is deleted between listing and processing
        print(f"[WARN] File {abs_file_path} was not found during metadata extraction (possibly deleted). Skipping.")
        return {}
    except Exception as e:
        print(f"Error processing file {abs_file_path}: {e}")
        return {}


# 4. Store Data in Redis Vector Sets
def store_in_redis(redis_client: redis.Redis, data: Dict[str, Any], vector_set_name: str) -> bool:
    """
    Stores file metadata and embedding in Redis.
    Uses a composite key: relative_file_path:commit_hash.
    """
    if not redis_client:
        print("Redis client is not initialized.")
        return False
    if not data or "embedding" not in data:  # Ensure data and embedding are present
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

        redis_client.hset(record_id, mapping=attributes)

        redis_client.vset().vadd(vector_set_name, vector, record_id)

        print(f"Successfully stored data for record: {record_id}")
        return True
    except redis.exceptions.ResponseError as e:
        print(
            f"Redis command error storing data for {data.get('relative_file_path', 'N/A')}:{data.get('commit_hash', 'N/A')}: {e}")
        print("Ensure the Redis Stack 'Vector Search' module is loaded and VS.SET command is available.")
        print("Also ensure VECTOR_SET_NAME is properly managed (e.g., created with VS.CREATE if needed).")
        return False
    except Exception as e:
        print(
            f"Error storing data in Redis for {data.get('relative_file_path', 'N/A')}:{data.get('commit_hash', 'N/A')}: {e}")
        return False


class ChangeHandler(FileSystemEventHandler):
    """Handles file system events and triggers App actions."""

    def __init__(self, app_instance, watch_path, redis_client, embedding_model):
        super().__init__()
        self.app = app_instance
        self.watch_path = os.path.abspath(watch_path)
        self.git_dir_to_ignore = os.path.join(self.watch_path, '.git')
        self.redis_client = redis_client
        self.embedding_model = embedding_model

        asyncio.run(self.listen())

    async def listen(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 30717))
            s.listen()
            conn, addr = s.accept()
            with conn:
                print(f"[NETWORK] Connected by {addr}")
                while True:
                    data = conn.recv(10000)
                    if not data:
                        break
                    await self.handle_network_request(conn, data)

    async def handle_network_request(self, conn, data):
        from searcher import analyze_search_query
        print("[INFO] analyzing search query")
        result = await analyze_search_query(data)
        if result:
            print("[INFO] performing redis vector similarity search")
            embedding = self.embedding_model.encode(result).tolist()
            res = self.redis_client.vset().vsim(VECTOR_SET_NAME, embedding, True, 3)
            print("[NETWORK] sending results")
            conn.send(json.dumps(res).encode('utf-8'))


    def _should_process(self, event_path):
        """Helper to decide if an event should be processed."""
        abs_event_path = os.path.abspath(event_path)
        filename = os.path.basename(abs_event_path)

        # Ignore events within the .git directory itself or any of its subdirectories.
        if abs_event_path.startswith(self.git_dir_to_ignore + os.sep) or abs_event_path == self.git_dir_to_ignore:
            # print(f"[DEBUG_WATCHDOG] Ignoring event in .git: {event_path}")
            return False

        # Ignore common problematic/temporary files by name or pattern.
        # These files are often created by OS or editors and are not user data.
        if filename == ".DS_Store" or \
                filename.endswith((".swp", ".swx", "~", ".tmp", ".TMP", ".part", ".crdownload", ".sage~")) or \
                filename.startswith(("~", ".~", "._", "NFS")):  # Added common temp/lock prefixes/suffixes
            # print(f"[DEBUG_WATCHDOG] Ignoring common/temp file: {filename}")
            return False

        # Only process .docx files for this application's embedding logic.
        if not filename.endswith(".docx"):
            # print(f"[DEBUG_WATCHDOG] Ignoring non-txt file: {filename} (event path: {event_path})")
            return False

        return True

    def _handle_event(self, event_path, event_type):
        """Generic handler for relevant file events."""
        if not self._should_process(event_path):
            return

        print(f"[WATCHDOG] Detected {event_type}: {event_path}")

        # Get relative path for Git operations
        # Ensure event_path is within self.app.path before making it relative
        try:
            if os.path.commonpath([self.app.path, os.path.abspath(event_path)]) != self.app.path:
                print(
                    f"[WARN_WATCHDOG] Event path {event_path} is outside the repository path {self.app.path}. Skipping.")
                return
            relative_path = os.path.relpath(event_path, self.app.path)
        except ValueError:
            print(
                f"[WARN_WATCHDOG] Could not determine relative path for {event_path} against {self.app.path}. Skipping.")
            return

        # Add the specific file/directory.
        # For deleted files, git add will stage the deletion.
        self.app.git_add(filepaths=relative_path)

        commit_message = f"Auto-commit: {event_type} on {relative_path}"
        asyncio.run(self.app.git_commit(commit_message))  # This will trigger embedding processing

    def on_created(self, event):
        super().on_created(event)
        if not event.is_directory:
            self._handle_event(event.src_path, "created")

    def on_modified(self, event):
        super().on_modified(event)
        if not event.is_directory:
            # For modified, ensure file still exists (might be part of a rename/delete sequence)
            if os.path.exists(event.src_path):
                self._handle_event(event.src_path, "modified")

    def on_deleted(self, event):
        super().on_deleted(event)
        if not event.is_directory:
            self._handle_event(event.src_path, "deleted")  # git_add will handle staging the deletion

    def on_moved(self, event):
        super().on_moved(event)
        # A move is a delete at src_path and create at dest_path
        # Git handles renames well if both are added.
        if not event.is_directory:
            print(f"[WATCHDOG] Detected moved: {event.src_path} to {event.dest_path}")
            if self._should_process(event.src_path):  # Process deletion part if relevant
                rel_src_path = os.path.relpath(event.src_path, self.app.path)
                self.app.git_add(filepaths=rel_src_path)  # Stage deletion of old path

            if self._should_process(event.dest_path):  # Process creation part if relevant
                rel_dest_path = os.path.relpath(event.dest_path, self.app.path)
                self.app.git_add(filepaths=rel_dest_path)  # Stage creation of new path

            # Commit both changes together
            commit_message = f"Auto-commit: moved {os.path.relpath(event.src_path, self.app.path)} to {os.path.relpath(event.dest_path, self.app.path)}"
            asyncio.run(self.app.git_commit(commit_message))


class App():
    def __init__(self):
        self.path = None
        self.repo = None
        print("[INFO] Initializing App: Connecting to Redis and loading embedding model...")
        self.redis_client = get_redis_connection()
        self.embedding_model = load_embedding_model()
        self.observer = None  # For watchdog

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
            # Check if it's already a git repo
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

    def git_add(self, filepaths='.'):
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

            if processed_filepaths == '.':  # Add all changes if '.'
                self.repo.git.add(A=True)
            else:  # Add specific file(s)
                self.repo.git.add(processed_filepaths)
            print("[INFO] Changes staged.")

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

        try:
            # (Optional) auto-stage everything:
            # self.repo.git.add(all=True)

            # === unified staged-change detection ===
            status = self.repo.git.status('--porcelain').splitlines()
            staged_changes = any(line and line[0] != ' ' for line in status)

            if not staged_changes:
                print("[INFO] No staged changes detected to commit.")
                if not self.repo.is_dirty(untracked_files=True):
                    print("[INFO] Working directory is also clean.")
                else:
                    print(f"[INFO] Working directory has changes not staged:\n"
                          f"{self.repo.git.status(s=True)}")
                return None

            print(f"[INFO] Attempting to commit staged changes with message: '{message}'")

            # === ensure user.name / user.email ===
            try:
                conf = self.repo.config_reader()
                if not conf.get_value('user', 'name', None) or not conf.get_value('user', 'email', None):
                    print("[ERROR_COMMIT] Missing git user.name/email. Please configure them.")
                    return None
            except Exception as e:
                print(f"[WARN_COMMIT] Could not verify git config: {e}")

            # === commit ===
            new_commit = self.repo.index.commit(message)
            print(f"[INFO] Commit successful. New commit SHA: {new_commit.hexsha}")

            # === collect affected .docx files ===
            affected = []
            if new_commit.parents:
                parent = new_commit.parents[0]
                for diff in parent.diff(new_commit):
                    if diff.change_type in ('A', 'M', 'R') and diff.b_path.endswith('.docx'):
                        affected.append(diff.b_path)
            else:
                for item in new_commit.tree.traverse():
                    if item.path.endswith('.docx'):
                        affected.append(item.path)

            affected = list(set(affected))
            if affected:
                print(f"[INFO] Processing embeddings for: {affected}")
                await self.process_committed_files_embeddings(new_commit.hexsha, affected)
            else:
                print(f"[INFO] No .docx files added/modified in this commit.")

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
        """Processes embeddings only for specified .docx files from a commit."""
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
            file_data = await process_file_and_get_data(
                abs_file_path,
                rel_path,
                self.embedding_model,
                commit_hash
            )
            if file_data:  # process_file_and_get_data returns {} on error or empty file
                store_in_redis(self.redis_client, file_data, VECTOR_SET_NAME)
                processed_count += 1
        print(f"[INFO] Finished processing embeddings for {processed_count} files from commit {commit_hash}.")

    def start_monitoring(self, directory_to_watch: str):
        """Starts monitoring the specified directory for file changes."""
        if not self.repo:
            print("[ERROR] Git repository not initialized. Cannot start monitoring effectively.")
            # Optionally, you could allow monitoring without Git, but the current flow depends on it.
            return

        event_handler = ChangeHandler(self, directory_to_watch, self.redis_client, self.embedding_model)
        # Optional: For more verbose watchdog logging, use LoggingEventHandler
        # logging_event_handler = LoggingEventHandler() # Logs all events to console

        self.observer = Observer()
        self.observer.schedule(event_handler, directory_to_watch, recursive=True)
        # self.observer.schedule(logging_event_handler, directory_to_watch, recursive=True) # If using

        print(f"[INFO] Starting file system monitor for: {directory_to_watch}")
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[INFO] Monitoring stopped by user (KeyboardInterrupt).")
        finally:
            self.observer.stop()
            self.observer.join()
            print("[INFO] File system monitor shut down.")

    def stop_monitoring(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            print("[INFO] File system monitor shut down by stop_monitoring call.")

def main():
    app = App()
    if not app.redis_client or not app.embedding_model:
        print("[EXIT] Cannot run example due to missing Redis connection or embedding model.")
        exit()

    # USER: Define the path to YOUR existing directory here
    user_repo_path = "../../workdir_monitor_test"  # Example path, CHANGE AS NEEDED
    user_repo_path = os.path.abspath(user_repo_path)

    if not os.path.exists(user_repo_path):
        print(f"[SETUP] Test directory {user_repo_path} does not exist. Creating it now.")
        os.makedirs(user_repo_path, exist_ok=True)
        print(f"[SETUP] Created test directory {user_repo_path}. You can now add/modify .docx files in it.")
    else:
        print(f"[SETUP] Using existing test directory: {user_repo_path}")

    app.init_directory(user_repo_path)

    if app.repo:
        # Optional: Perform an initial commit of existing files if the repo is new/has uncommitted changes
        print("\n[INFO] Checking for initial uncommitted changes...")
        app.git_add('.')  # Stage everything initially
        initial_commit_hash = asyncio.run(app.git_commit("Initial commit of existing files upon startup"))
        if initial_commit_hash:
            print(f"Initial commit successful: {initial_commit_hash}")
        else:
            print("No initial changes to commit, or commit failed.")

        # Start monitoring
        app.start_monitoring(user_repo_path)
    else:
        print(f"[ERROR] Repository not initialized at {user_repo_path}. Cannot start monitoring.")

    print("\n--- Script End (or should be if monitoring was not started/stopped) ---")
    if app.redis_client:
        app.redis_client.close()  # This might not be reached if monitoring runs indefinitely
        print("Redis connection closed.")
# Example Usage

if __name__ == '__main__':
    main()
