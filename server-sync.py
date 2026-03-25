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
    connection.sendall(
        f"[server] Connected! Welcome {addr}. "
        f"Commands: /list  /upload <file>  /download <file>\n".encode()
    )
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