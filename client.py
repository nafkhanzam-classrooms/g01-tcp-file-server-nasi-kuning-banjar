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