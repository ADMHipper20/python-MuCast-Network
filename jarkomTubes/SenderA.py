import socket
import struct
import time
import os

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

def send_file_multicast(file_path, multicast_group, port):
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Set TTL for multicast
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    
    try:
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Send file info first
        file_name = os.path.basename(file_path)
        file_info = f"{file_name}|{file_size}"
        sock.sendto(file_info.encode(), (multicast_group, port))
        time.sleep(0.1)  # Small delay to ensure receivers get the info
        
        # Send file content
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(1024)
                if not chunk:
                    break
                sock.sendto(chunk, (multicast_group, port))
                time.sleep(0.01)  # Small delay to prevent overwhelming the network
        
        # Send end marker
        sock.sendto(b"DONE", (multicast_group, port))
        print(f"File {file_name} sent successfully!")
        
    except Exception as e:
        print(f"Error sending file: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    # Multicast configuration
    MULTICAST_GROUP = '224.3.29.71'
    PORT = 10000
    
    while True:
        print("\nMulticast File Sender")
        print("1. Send a file")
        print("2. Exit")
        choice = input("Enter your choice (1-2): ")
        
        if choice == '1':
            file_path = input("Enter the path of the file to send: ")
            if os.path.exists(file_path):
                send_file_multicast(file_path, MULTICAST_GROUP, PORT)
            else:
                print("File not found!")
        elif choice == '2':
            print("Exiting...")
            break
        else:
            print("Invalid choice!") 