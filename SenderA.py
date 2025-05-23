import socket
import struct
import time
import os
import threading

# Valid tokens for receivers and their corresponding channels/names
VALID_CHANNELS = {
    "channel_alpha_token": "Channel Alpha", # Example channel 1
    "channel_beta_token": "Channel Beta" # Example channel 2
}

# Dictionary to store authenticated receiver addresses for each channel
authenticated_receivers = {}

def get_filetype(file_name):
    if file_name.endswith('.html'):
        return "text/html"
    elif file_name.endswith(('.jpg', '.jpeg')):
        return "image/jpeg"
    elif file_name.endswith('.png'):
        return "image/png"
    elif file_name.endswith('.gif'):
        return "image/gif"
    elif file_name.endswith('.css'):
        return "text/css"
    elif file_name.endswith('.js'):
        return "text/javascript"
    elif file_name.endswith('.mp3'):
        return "audio/mpeg"
    elif file_name.endswith('.mp4'):
        return "video/mp4"
    else:
        return "application/octet-stream"

def handle_multicast_traffic(sock, multicast_group, port):
    print(f"Sender listening on {multicast_group}:{port} for authentication requests")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode()
            
            if message.startswith("JOIN_CHANNEL|"):
                parts = message.split('|')
                if len(parts) == 3:
                    command, token, channel_name = parts
                    if token in VALID_CHANNELS and VALID_CHANNELS[token] == channel_name:
                        if channel_name not in authenticated_receivers:
                            authenticated_receivers[channel_name] = {}
                        # Add receiver address to the authenticated list for this channel
                        authenticated_receivers[channel_name][addr] = True
                        print(f"Receiver {addr} successfully joined channel '{channel_name}'")
                        # Optional: Send a direct acknowledgment back to the receiver
                        # sock.sendto(f"JOIN_SUCCESS|{channel_name}".encode(), addr)
                    else:
                        print(f"Invalid JOIN_CHANNEL attempt from {addr} with token '{token}' for channel '{channel_name}'")
                        # Optional: Send a direct rejection back to the receiver
                        # sock.sendto(b"JOIN_FAILED", addr)
                else:
                     print(f"Invalid JOIN_CHANNEL message format from {addr}")
            # We can add handling for other control messages here later if needed
            
        except Exception as e:
            print(f"Error in multicast traffic handler: {e}")
            break

def send_file_multicast(file_path, multicast_group, port, channel_name):
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Set TTL for multicast
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    
    try:
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Include channel name in the file info
        file_name = os.path.basename(file_path)
        file_info = f"FILE_INFO|{channel_name}|{file_name}|{file_size}"
        sock.sendto(file_info.encode(), (multicast_group, port))
        time.sleep(0.1)  # Small delay to ensure receivers get the info
        
        # Send file content
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(1024)
                if not chunk:
                    break
                # Tag data chunks with channel name (optional but good practice)
                # data_chunk_message = f"FILE_DATA|{channel_name}|".encode() + chunk
                sock.sendto(chunk, (multicast_group, port))
                time.sleep(0.01)  # Small delay
        
        # Send end marker
        # end_marker_message = f"DONE|{channel_name}".encode()
        sock.sendto(b"DONE", (multicast_group, port))
        print(f"File {file_name} sent successfully to channel '{channel_name}'!")
        
    except Exception as e:
        print(f"Error sending file: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    # Multicast configuration
    MULTICAST_GROUP = '224.3.29.71'
    MULTICAST_PORT = 10000
    
    # Create socket for multicast traffic (both sending and receiving control messages)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind to the multicast port
    sock.bind(('', MULTICAST_PORT))
    
    # Tell the kernel to join the multicast group on the sender side (can be useful)
    mreq = struct.pack('4sL', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    # Start thread to handle incoming multicast traffic (authentication requests)
    multicast_handler_thread = threading.Thread(target=handle_multicast_traffic, args=(sock, MULTICAST_GROUP, MULTICAST_PORT))
    multicast_handler_thread.daemon = True
    multicast_handler_thread.start()
    
    while True:
        print("\nMulticast File Sender")
        print("Available Channels:")
        for token, name in VALID_CHANNELS.items():
            print(f"- {name} (Token: {token})")
        print("1. Send a file to a channel")
        print("2. Exit")
        choice = input("Enter your choice (1-2): ")
        
        if choice == '1':
            channel_token_input = input("Enter the token for the channel you want to send to: ")
            if channel_token_input in VALID_CHANNELS:
                channel_name = VALID_CHANNELS[channel_token_input]
                file_path = input("Enter the path of the file to send: ")
                if os.path.exists(file_path):
                    # Check if there are any authenticated receivers for this channel (optional)
                    # if channel_name in authenticated_receivers and authenticated_receivers[channel_name]:
                    print(f"Sending file to channel '{channel_name}'...")
                    send_file_multicast(file_path, MULTICAST_GROUP, MULTICAST_PORT, channel_name)
                    # else:
                    #     print(f"No authenticated receivers for channel '{channel_name}'. File not sent.")
                else:
                    print("File not found!")
            else:
                print("Invalid channel token!")
        elif choice == '2':
            print("Exiting...")
            break
        else:
            print("Invalid choice!")

    sock.close() 