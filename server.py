import socket # basic socket package of python
import threading
import os
import uuid # supports generation of unique identifiers to prevent same name file errors/overwrites

# Server IP and port configuration
SERVER_IP = "0.0.0.0"  # Listen on all available network interfaces
SERVER_PORT = 9000      # Port number where the server will listen for connections

# Dictionary to store connected clients
# Key: client socket, Value: client name
clients = {}  # {socket: name}

# Function to receive exactly 'n' bytes from a socket
def recvall(sock, n):
    data = b""  # Initialize an empty byte string to store received data
    while len(data) < n:  # Keep receiving until we get 'n' bytes
        packet = sock.recv(n - len(data))  # Receive remaining bytes
        if not packet:  # If connection is closed or no data, return None
            return None
        data += packet  # Append received bytes to our data buffer
    return data

# Function to send data to a specific client or all clients
def send_to(name_target, data, sender_socket):
    #If 'name_target' is 'all', it broadcasts to all connected clients except the sender.
    if name_target == "all":
        # Broadcast to all clients except the sender
        for client, _ in clients.items():
            if client != sender_socket:
                try:
                    client.sendall(data)  # Send the data
                except:
                    clients.pop(client, None)  # Remove client if sending fails
    else:
        # Send to a specific client
        for client, name in clients.items():
            if name == name_target and client != sender_socket:
                try:
                    client.sendall(data)
                except:
                    clients.pop(client, None)  # Remove client if sending fails
                break

# Function to handle communication with a single client
def handle_client(client_socket, addr):
    try:
        # Receive the client's name (terminated by newline '\n')
        name_bytes = b""
        while b"\n" not in name_bytes:
            chunk = client_socket.recv(1)  # Receive one byte at a time
            if not chunk:
                return  # Connection closed before sending name
            name_bytes += chunk
        name = name_bytes.decode().strip()  # Decode bytes to string and remove whitespace
        clients[client_socket] = name  # Store the client in the clients dictionary
        print(f"[Connection] {addr} joined as '{name}'")

        # Main loop to handle client messages and file transfers
        while True:
            # Receive message header (terminated by newline '\n')
            header_bytes = b""
            while b"\n" not in header_bytes:
                chunk = client_socket.recv(1)
                if not chunk:
                    raise ConnectionResetError()  # Client disconnected unexpectedly
                header_bytes += chunk
            header = header_bytes.decode().strip()  # Convert bytes to string
            
            # prevent empty strings
            if not header:
                continue
            
            parts = header.split("|")  # Split header into parts

            # Check the type of data: message, list request, or file
            if parts[0] == "MSG":
                # Message handling
                sender_name = parts[1]
                recipient = parts[2]  # 'all' for broadcast
                length = int(parts[3])  # Message length in bytes
                message = recvall(client_socket, length).decode()  # Receive the full message
                out_header = f"MSG|{sender_name}|{recipient}|{length}|\n" # standardize header ofr recipient
                full_packet = (out_header + message).encode() # prevent data fragmenting
                if recipient != "all":
                    send_to(recipient, full_packet, client_socket)
                    print(f"[{sender_name} -> {recipient}] {message}")
                else:
                    send_to("all", full_packet, client_socket)
                    print(f"[{sender_name} -> everyone] {message}")
            
            elif parts[0] == "LIST":
                # List command handling
                sender_name = parts[1]
                user_list = ", ".join(clients.values()) # obtain list of users
                response = f"SYSTEM: Online users: {user_list}" #
                resp_header = f"MSG|Server|{sender_name}|{len(response)}|\n".encode()
                client_socket.sendall(resp_header + response.encode())
                print(f"[{sender_name} requested list of users]")

            elif parts[0] == "FILE":
                # File transfer handling
                sender_name = parts[1]
                recipient = parts[2]
                filename = parts[3]
                filesize = int(parts[4])
                print(f"[File {sender_name} -> {recipient}] Receiving {filename} ({filesize} bytes)")
                
                # Temporary storage for the file on the server with unique identifier to prevent overwriting
                uniq_id = str(uuid.uuid4())[:8]
                filepath = f"tmp_{uniq_id}_{filename}"
                print(f"[File] Recieving {filename} from {sender_name}. Saving to {filepath}")
                with open(filepath, "wb") as f:
                    remaining = filesize
                    while remaining > 0:
                        chunk = client_socket.recv(min(4096, remaining))  # Receive in chunks
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                
                # Send the file to the recipient(s)
                with open(filepath, "rb") as f:
                    file_header = f"FILE|{sender_name}|{filename}|{filesize}\n".encode()
                    send_to(recipient, file_header, client_socket)
                    while chunk := f.read(4096):  # Read file in chunks
                        send_to(recipient, chunk, client_socket)
                
                os.remove(filepath)  # Delete temporary file
                print(f"[File {filename}] sent to {recipient}")

    except ConnectionResetError:
        print(f"[Unexpected Disconnect] {clients.get(client_socket, addr)}")
    except Exception as e:
        print(f"[Error {clients.get(client_socket, addr)}] {e}")
    finally:
        # Cleanup when client disconnects
        if client_socket in clients:
            print(f"[Disconnected] {clients[client_socket]}")
            clients.pop(client_socket)
        client_socket.close()

# Main function to start the server
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create TCP socket
    server.bind((SERVER_IP, SERVER_PORT))  # Bind socket to IP and port
    server.listen()  # Start listening for incoming connections
    print(f"[Server] Listening on {SERVER_IP}:{SERVER_PORT}")

    # Infinite loop to accept clients
    while True:
        client_socket, addr = server.accept()  # Accept new connection
        # Start a new thread for each client
        thread = threading.Thread(target=handle_client, args=(client_socket, addr), daemon=True)
        thread.start()

# Entry point of the script
if __name__ == "__main__":
    main()