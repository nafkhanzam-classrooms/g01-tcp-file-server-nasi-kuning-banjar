import socket
import threading
import os

FILES_DIR = "server_files"
os.makedirs(FILES_DIR, exist_ok=True)

class Server:
  def __init__(self):
      self.host = 'localhost'
      self.port = 5003
      self.server = None
      self.threads = []
      self.clients_lock = threading.Lock()
      self.clients = []

  def open_socket(self):
      self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      self.server.bind((self.host, self.port))
      self.server.listen(5)

  def run(self):
    self.open_socket()
    print(f"[thread] Listening on {self.host}:{self.port} ...")
    try:
      while True:
        # New client: spawn a thread
        client_sock, client_addr = self.server.accept()
        c = Client(client_sock, client_addr, self)
        with self.clients_lock:
            self.clients.append(c)
        c.start()
        self.threads.append(c)
        print("Connected:", client_addr)
    except KeyboardInterrupt:
        pass

    self.server.close()
    for c in self.threads:
        c.join()

  def broadcast(self, sender, msg_bytes):
    with self.clients_lock:
        for c in self.clients:
            if c is not sender:
                try:
                    c.client.sendall(msg_bytes)
                except Exception:
                    pass

  def remove_client(self, client_obj):
    with self.clients_lock:
        if client_obj in self.clients:
            self.clients.remove(client_obj)


class Client(threading.Thread):
  def __init__(self, client, address, server):
      threading.Thread.__init__(self)
      self.client = client
      self.address = address
      self.server  = server
      self.size    = 4096
      self.pending_upload = None

  def recv_exact(self, n):
    buf = b""
    while len(buf) < n:
        chunk = self.client.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError
        buf += chunk
    return buf


  def run(self):
      try:
          while True:
              data = self.client.recv(self.size)
              if not data:
                  break

              if self.pending_upload is not None:
                  filepath, file_size, received, fobj, size_buf = self.pending_upload

                  if file_size == -1:
                      size_buf += data
                      if len(size_buf) >= 8:
                          file_size = int.from_bytes(size_buf[:8], "big")
                          leftover  = size_buf[8:]
                          fobj = open(filepath, "wb")
                          self.pending_upload = [filepath, file_size, 0, fobj, b""]
                          if leftover:
                              fobj.write(leftover)
                              self.pending_upload[2] += len(leftover)
                      else:
                          self.pending_upload[4] = size_buf
                  else:
                      fobj.write(data)
                      self.pending_upload[2] += len(data)

                  state = self.pending_upload
                  if state[1] != -1 and state[2] >= state[1]:
                      state[3].close()
                      name = os.path.basename(state[0])
                      self.client.sendall(f"Uploaded '{name}' ({state[2]} bytes).".encode())
                      print(f"Saved '{name}' ({state[2]} bytes)")
                      self.pending_upload = None
                  continue

              msg = data.decode(errors="replace").strip()
              print("received:", self.address, msg)

              if msg.startswith("/list"):
                  files = os.listdir(FILES_DIR)
                  reply = "\n".join(files) if files else "(no files)"
                  self.client.sendall(reply.encode())

              elif msg.startswith("/upload "):
                  filename = msg.split(" ", 1)[1].strip()
                  filepath = os.path.join(FILES_DIR, os.path.basename(filename))
                  self.pending_upload = [filepath, -1, 0, None, b""]
                  self.client.sendall(b"READY")

              elif msg.startswith("/download "):
                  filename = msg.split(" ", 1)[1].strip()
                  filepath = os.path.join(FILES_DIR, os.path.basename(filename))
                  if not os.path.isfile(filepath):
                      self.client.sendall(b"ERROR File not found")
                  else:
                      file_size = os.path.getsize(filepath)
                      self.client.sendall(b"OK" + file_size.to_bytes(8, "big"))
                      with open(filepath, "rb") as f:
                          while True:
                              chunk = f.read(self.size)
                              if not chunk:
                                  break
                              self.client.sendall(chunk)
                      print(f"Sent '{filename}' ({file_size} bytes)")

              else:
                  broadcast_msg = f"[{self.address}] {msg}".encode()
                  self.server.broadcast(self, broadcast_msg)
                  self.client.sendall(b"[you] " + msg.encode())

      except (ConnectionResetError, BrokenPipeError, OSError):
          pass
      finally:
          self.client.close()
          self.server.remove_client(self)
          print("Disconnected:", self.address)

if __name__ == '__main__':
    server = Server()
    server.run()
