[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama           | NRP        | Kelas     |
| ---            | ---        | ----------|
|Severinus Fabian Tanuwidjaja |50252411110 |D |
|Hanif Aqil Janardana |5025241111 |D |

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```
https://youtu.be/BK9EluVqiF8
```

## Penjelasan Program
### server-sync.py
```
import socket
import os

HOST = '0.0.0.0'
PORT = 5000
BUFFER = 4096

FILES_DIR = "server_files"
os.makedirs(FILES_DIR, exist_ok=True)

server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST,PORT))
server_socket.listen(5)
print(f"[sync] Listening on {HOST}:{PORT} …")

while True:
    connection, addr = server_socket.accept()
    print(f"Connected: {addr}")
    try:
        while True:
            msg = connection.recv(1024).decode()
            if not msg:
                break
            parts = msg.split()

            if msg.startswith("/list"):
                files = os.listdir(FILES_DIR)
                if not files:
                    connection.sendall(b"EMPTY")
                else:
                    connection.sendall("\n".join(files).encode())

            elif msg.startswith("/upload "):
                if len(parts) < 3:
                    connection.sendall(b"INVALID COMMAND")
                    connection.close()
                    continue

                filename = parts[1]
                file_size = int(parts[2])
                filepath = os.path.join(FILES_DIR, os.path.basename(filename))
                connection.sendall(b"READY")
                with open(filepath, "wb") as f:
                    remaining = file_size
                    while remaining > 0:
                        data = connection.recv(min(4096, remaining))
                        if not data:
                            break
                        f.write(data)
                        remaining -= len(data)
                connection.sendall(f"Uploaded '{filename}' ({file_size} bytes)".encode())
                print(f"Saved '{filename}' ({file_size} bytes)")

            elif msg.startswith("/download "):
                filename = parts[1]
                filepath = os.path.join(FILES_DIR, os.path.basename(filename))
                if not os.path.exists(filepath):
                    connection.sendall(b"ERROR File not found")
                else:
                    file_size = os.path.getsize(filepath)
                    connection.sendall(b"OK" + file_size.to_bytes(8, "big"))
                    with open(filepath, "rb") as f:
                        while chunk := f.read(1024):
                            connection.sendall(chunk)
                    print(f"Sent '{filename}' ({file_size} bytes)")

            else: 
                connection.sendall(b"[echo] " + msg.encode())
                print(f"[{addr}] {msg}")

    except Exception as e:
        print("Error:", e)

    finally:
        connection.close()
        print(f"Disconnected: {addr}")
```
#### Penjelasan
server melakukan bind pada port 5000 dan akan menerima koneksi dengan satu client. Jika adal client lain yang ingin melakukan koneksi, maka akan masuk kedalam antrian yang nantinya akan langsung terkoneksi Ketika client sebelumnya disconnect. Server menghandle command dengan membagi pesan menjadi beberapa bagian. Untuk command `/list` server akan mengirimkan hasil listdir ke client. Untuk command `/upload` server akan menerima nama file dan ukurannya dari client yang kemudian menerima filenya.
Untuk command `/download` server akan mencari filenya dan mengirimkan ukuran filenya terlebih dahulu lalu kemudian mengirim file tujuan.


### server-select.py
```
import select
import socket
import os

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('0.0.0.0', 5001))
server_socket.listen()

FILES_DIR = "server_files"
os.makedirs(FILES_DIR, exist_ok=True)

input_sockets = [server_socket]
pending_uploads = {}

while True:
    read_ready, _, _ = select.select(input_sockets, [], [])

    for sock in read_ready:
        if sock == server_socket:
            client_sock, client_addr = server_socket.accept()
            input_sockets.append(client_sock)
            print("Connected:", client_addr)
        else:
            data = sock.recv(4096)

            if not data:
                addr = sock.getpeername()
                sock.close()
                input_sockets.remove(sock)
                pending_uploads.pop(sock, None)
                print("Disconnected:", addr)
                continue

            if sock in pending_uploads:
                state = pending_uploads[sock]
                filepath, file_size, received, fobj, size_buf = state
                if file_size == -1:
                    size_buf += data
                    if len(size_buf) >= 8:
                        file_size = int.from_bytes(size_buf[:8], "big")
                        leftover  = size_buf[8:]
                        fobj = open(filepath, "wb")
                        pending_uploads[sock] = [filepath, file_size, 0, fobj, b""]
                        if leftover:
                            fobj.write(leftover)
                            pending_uploads[sock][2] += len(leftover)
                    else:
                        pending_uploads[sock][4] = size_buf
                else:
                    fobj.write(data)
                    pending_uploads[sock][2] += len(data)

                state = pending_uploads[sock]
                if state[1] != -1 and state[2] >= state[1]:
                    state[3].close()
                    name = os.path.basename(state[0])
                    sock.sendall(f"Uploaded '{name}' ({state[2]} bytes).".encode())
                    print(f"Saved '{name}' ({state[2]} bytes)")
                    del pending_uploads[sock]
                continue 
                
            msg = data.decode(errors="replace").strip()
            print(sock.getpeername(), msg)

            if msg.startswith("/list"):
                files = os.listdir(FILES_DIR)
                reply = "\n".join(files) if files else "(no files)"
                sock.sendall(reply.encode())

            elif msg.startswith("/upload "):
                filename = msg.split(" ", 1)[1].strip()
                filepath = os.path.join(FILES_DIR, os.path.basename(filename))
                pending_uploads[sock] = [filepath, -1, 0, None, b""]
                sock.sendall(b"READY")

            elif msg.startswith("/download "):
                filename = msg.split(" ", 1)[1].strip()
                filepath = os.path.join(FILES_DIR, os.path.basename(filename))
                if not os.path.isfile(filepath):
                    sock.sendall(b"ERROR File not found")
                else:
                    file_size = os.path.getsize(filepath)
                    sock.sendall(b"OK" + file_size.to_bytes(8, "big"))
                    with open(filepath, "rb") as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            sock.sendall(chunk)
                    print(f"Sent '{filename}' ({file_size} bytes)")

            else:
                broadcast_msg = f"[{sock.getpeername()}] {msg}".encode()
                for other in input_sockets:
                    if other != server_socket and other != sock:
                        try:
                            other.sendall(broadcast_msg)
                        except Exception:
                            pass
                sock.sendall(b"[you] " + msg.encode())

```
#### Penjelasan
    server-select.py mengimport library select. Proses binding dan listening dilakukan seperti biasa, perbedaan utama berada di hadirnya list pending_upload untuk menyimpan data file yang diupload oleh client dan dikelola dalam while loop.
    While loop dimulai dengan mencari client dan menerima koneksi client, jika ada maka server akan melakukan koneksi terhadap client. Jika belum terdeteksi adanya data pada read_ready, maka server akan mencoba melakukan receive data. Jika tidak ada data yang terjadi maka server akan terputus dari client. Pengaturan dari upload akan dicek dari pending_upload yang akan mengurai data file sehingga dikirimkan per chunk yang sesuai. Untuk mengatasi setiap command yang diberikan (/list, /upload, /download), kami membuat handler dengan mengecek input spesifik dari user seperti pada server-sync.py.
    Perbedaan lain yang terlihat dibanding dengan server-select.py adalah adanya broadcast yang terjadi ketika client menginput selain dari command yang diberikan sebelumnya. Di proses ini, client mengirimkan segala hal yang dia tulis, diterima server, dan disebarkan server ke semua client yang saat itu sedang terkoneksi dengannya. Dengan ini, client bisa mengetahui asal dari setiap pesan yang diterima.
    
### server-poll.py
```
import select
import socket
import os

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 5002))
server.listen()
server.setblocking(False)

FILES_DIR = "server_files"
os.makedirs(FILES_DIR, exist_ok=True)

poll_obj = select.poll()
poll_obj.register(server.fileno(), select.POLLIN)

fd_map    = {server.fileno(): server}
pending_uploads = {}

while True:
  for fd, event in poll_obj.poll():
    sock = fd_map[fd]

  if sock is server:
    conn, addr = server.accept()
    conn.setblocking(False)
    fd_map[conn.fileno()] = conn
    poll_obj.register(conn.fileno(), select.POLLIN)
    print('Connected:', addr)

  elif event & select.POLLIN:
    try:
      data = sock.recv(4096)
    except:
      data = b''
    if not data:
      addr = sock.getpeername()
      poll_obj.unregister(fd)
      del fd_map[fd]
      pending_uploads.pop(sock, None)
      sock.close()
      print("Disconnected:", addr)
      continue

    if sock in pending_uploads:
      state = pending_uploads[sock]
      filepath, file_size, received, fobj, size_buf = state

      if file_size == -1:
        size_buf += data
        if len(size_buf) >= 8:
          file_size = int.from_bytes(size_buf[:8], "big")
          leftover  = size_buf[8:]
          fobj = open(filepath, "wb")
          pending_uploads[sock] = [filepath, file_size, 0, fobj, b""]
          if leftover:
              fobj.write(leftover)
              pending_uploads[sock][2] += len(leftover)
        else:
          pending_uploads[sock][4] = size_buf
      else:
        fobj.write(data)
        pending_uploads[sock][2] += len(data)

      state = pending_uploads[sock]
      if state[1] != -1 and state[2] >= state[1]:
          state[3].close()
          name = os.path.basename(state[0])
          sock.sendall(f"Uploaded '{name}' ({state[2]} bytes).".encode())
          print(f"Saved '{name}' ({state[2]} bytes)")
          del pending_uploads[sock]
      continue

    msg = data.decode(errors="replace").strip()
    print(sock.getpeername(), msg)

    if msg.startswith("/list"):
      files = os.listdir(FILES_DIR)
      reply = "\n".join(files) if files else "(no files)"
      sock.sendall(reply.encode())

    elif msg.startswith("/upload "):
      filename = msg.split(" ", 1)[1].strip()
      filepath = os.path.join(FILES_DIR, os.path.basename(filename))
      pending_uploads[sock] = [filepath, -1, 0, None, b""]
      sock.sendall(b"READY")

    elif msg.startswith("/download "):
      filename = msg.split(" ", 1)[1].strip()
      filepath = os.path.join(FILES_DIR, os.path.basename(filename))
      if not os.path.isfile(filepath):
          sock.sendall(b"ERROR File not found")
      else:
        file_size = os.path.getsize(filepath)
        sock.sendall(b"OK" + file_size.to_bytes(8, "big"))
        with open(filepath, "rb") as f:
          while True:
            chunk = f.read(4096)
            if not chunk:
              break
            sock.sendall(chunk)
        print(f"Sent '{filename}' ({file_size} bytes)")

    else:
      broadcast_msg = f"[{sock.getpeername()}] {msg}".encode()
      for other_sock in list(fd_map.values()):
        if other_sock is not server and other_sock is not sock:
          try:
            other_sock.sendall(broadcast_msg)
          except Exception:
            pass
      sock.sendall(b"[you] " + msg.encode())


  elif event & (select.POLLHUP | select.POLLERR):
    addr = sock.getpeername()
    poll_obj.unregister(fd)
    del fd_map[fd]
    pending_uploads.pop(sock, None)
    sock.close()
    print("Disconnected:", addr)


```
#### Penjelasan

### server-thread.py
```
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

```
#### Penjelasan

### client.py
```
import socket
import os
import threading

HOST = input("Server IP (default 127.0.0.1): ").strip() or "127.0.0.1"
PORT = input("Server port (5000/5001/5002/5003): ").strip()
PORT = int(PORT) if PORT else 5001

BUFFER      = 4096
DOWNLOADS   = "downloads"
os.makedirs(DOWNLOADS, exist_ok=True)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))
print(f"Connected to {HOST}:{PORT}")
print("Commands: /list  /upload <file>  /download <file>  /quit")

stop_event = threading.Event()

def listener():
    while not stop_event.is_set():
        try:
            client_socket.settimeout(1.0)
            data = client_socket.recv(BUFFER)
            if not data:
                print("\n[!] Server closed the connection.")
                stop_event.set()
                break
            print(f"\n{data.decode(errors='replace')}\n> ", end="", flush=True)
        except socket.timeout:
            continue
        except OSError:
            break

def recv_exact(n):
    buf = b""
    while len(buf) < n:
        chunk = client_socket.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("Server closed connection")
        buf += chunk
    return buf


def recv_text():
    data = client_socket.recv(BUFFER)
    if not data:
        raise ConnectionResetError("Server closed connection")
    return data.decode(errors="replace")

def upload(filepath):
    if not os.path.isfile(filepath):
        print(f"[!] File not found: {filepath}")
        return

    filename  = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)

    if PORT == 5000:
        client_socket.sendall(f"/upload {filename} {file_size}".encode())
        ack = recv_text()
        if ack != "READY":
            print(f"[!] Unexpected response: {ack}")
            return

        with open(filepath,"rb") as f:
            while chunk := f.read(BUFFER):
                client_socket.sendall(chunk)

    else:
        client_socket.sendall(f"/upload {filename}".encode())

        ack = recv_text()
        if ack != "READY":
            print(f"[!] Unexpected response: {ack}")
            return

        client_socket.sendall(file_size.to_bytes(8, "big"))

        sent = 0
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(BUFFER)
                if not chunk:
                    break
                client_socket.sendall(chunk)
                sent += len(chunk)
                pct = sent * 100 // file_size
                print(f"\r  uploading ... {pct}%", end="", flush=True)
        print()
    print(f"[ok] {recv_text()}")


def download(filename):
    client_socket.sendall(f"/download {filename}".encode())

    header = recv_exact(2)

    if header == b"OK":
        file_size = int.from_bytes(recv_exact(8), "big")
        filepath  = os.path.join(DOWNLOADS, os.path.basename(filename))
        received  = 0
        with open(filepath, "wb") as f:
            while received < file_size:
                chunk = client_socket.recv(min(BUFFER, file_size - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
                pct = received * 100 // file_size
                print(f"\r  downloading ... {pct}%", end="", flush=True)
        print()
        print(f"[ok] Saved to '{filepath}' ({received} bytes)")

    else:
        rest = client_socket.recv(BUFFER)
        print(f"[!] {(header + rest).decode(errors='replace')}")


t = threading.Thread(target=listener, daemon=True)
t.start()

while not stop_event.is_set():
    try:
        line = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        break

    if not line:
        continue
    if line in ("/quit", "/exit"):
        break

    elif line == "/list":
        stop_event.set()
        t.join(timeout=1.5)
        client_socket.sendall(b"/list")
        print(recv_text())
        stop_event.clear()
        t = threading.Thread(target=listener, daemon=True)
        t.start()

    elif line.startswith("/upload "):
        filepath = line.split(" ", 1)[1].strip()
        stop_event.set()
        t.join(timeout=1.5)
        upload(filepath)
        stop_event.clear()
        t = threading.Thread(target=listener, daemon=True)
        t.start()

    elif line.startswith("/download "):
        filename = line.split(" ", 1)[1].strip()
        stop_event.set()
        t.join(timeout=1.5)
        download(filename)
        stop_event.clear()
        t = threading.Thread(target=listener, daemon=True)
        t.start()

    else:
        client_socket.sendall(line.encode())

stop_event.set()
client_socket.close()
print("Disconnected.")
```
#### Penjelasan
Sebelum connect ke server client.py akan meminta input host dan port tujuan. Kemudian client akan membuat thread yang akan digunakan untuk menerima broadcast dari server. Client kemudian mengirimkan pesan atau command kepada server tujuan. Untuk command `/list` client akan menerima respon dari server yeng kemudian di print. Untuk command `/upload` client akan mengirimkan pesan dengan nama file dan ukuran untuk server-sync.py atau nama file saja untuk server lainnya lalu mengirimkan file ke server. Untuk command `/download` client akan mengirimkan nama file lalu menerima ukuran file dari server lalu menerima file yang dikirimkan. Untuk pesan selain command maka akan dikirimkan sebagai string yang kemudian di broadcast oleh server

## Screenshot Hasil

Kondisi awal folder

<img width="213" height="181" alt="image" src="https://github.com/user-attachments/assets/c4907dbd-c4d7-4278-9329-f7db1b9a0ebf" />

server-sync.py

<img width="1395" height="352" alt="image" src="https://github.com/user-attachments/assets/2e831e1d-00de-4dd6-9b2d-656b0ed8661a" />

Kondisi folder terbaru

<img width="223" height="241" alt="image" src="https://github.com/user-attachments/assets/19266d55-08d6-4028-a186-25f0ce821d22" />

server-select.py

<img width="1497" height="468" alt="image" src="https://github.com/user-attachments/assets/a9ac3071-f0bf-4e83-8aac-b038772dba37" />

Kondisi folder terbaru

<img width="224" height="308" alt="image" src="https://github.com/user-attachments/assets/383dbfe1-2f04-4221-980b-f6ae24d9a877" />

server-poll.py

<img width="1468" height="469" alt="image" src="https://github.com/user-attachments/assets/8481376b-8dde-4788-bf5e-28b1fa387ee4" />

kondisi folder terbaru

<img width="227" height="376" alt="image" src="https://github.com/user-attachments/assets/5e86e02b-dcce-44ba-b1d9-5bb28dd98180" />

server-thread.py

<img width="1470" height="435" alt="image" src="https://github.com/user-attachments/assets/ea437ae6-57f3-4ccc-89aa-98f726d97edd" />

Kondisi folder terbaru

<img width="222" height="368" alt="image" src="https://github.com/user-attachments/assets/3af6ef15-1561-4d89-8ea8-a75bf32af66d" />
