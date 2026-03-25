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
      # broadcast to all other clients
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

