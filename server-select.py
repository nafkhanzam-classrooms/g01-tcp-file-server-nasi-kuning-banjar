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
                continue   # ← still inside the upload if-block, just dedented correctly

            # ← text commands now outside the upload block
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
