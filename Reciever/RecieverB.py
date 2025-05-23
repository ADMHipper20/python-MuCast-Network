import socket
import struct
import os
import threading
import queue
import hashlib
import sys
import time

def get_unique_filename(save_dir, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    
    while os.path.exists(os.path.join(save_dir, new_filename)):
        new_filename = f"{base} ({counter}){ext}"
        counter += 1
    
    return new_filename

def receive_file_multicast(multicast_group, port, token, channel_name, save_dir='received_files'):
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Allow multiple sockets to use the same port
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind to the server address
    sock.bind(('', port))
    
    # Tell the kernel to join a multicast group
    mreq = struct.pack('4sL', socket.inet_aton(multicast_group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    # Create save directory if it doesn't exist
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    print(f"Receiver B for channel '{channel_name}' listening on {multicast_group}:{port}")
    
    # Send JOIN_CHANNEL message to sender
    join_message = f"JOIN_CHANNEL|{token}|{channel_name}"
    sock.sendto(join_message.encode(), (multicast_group, port))
    print(f"Sent JOIN_CHANNEL message for channel '{channel_name}'")
    
    # Queue for file processing
    file_queue = queue.Queue()
    
    def process_file():
        while True:
            try:
                file_data = file_queue.get()
                if file_data is None:
                    break
                    
                # Check if the file data is for this receiver's channel
                received_channel_name, file_name, file_size, data_chunks = file_data
                
                if received_channel_name == channel_name:
                    # Get unique filename
                    unique_filename = get_unique_filename(save_dir, file_name)
                    save_path = os.path.join(save_dir, unique_filename)
                    
                    print(f"\nProcessing file for channel '{channel_name}': {unique_filename}")
                    print(f"File size: {file_size} bytes")
                    
                    with open(save_path, 'wb') as file:
                        for chunk in data_chunks:
                            file.write(chunk)
                    
                    print(f"File {unique_filename} saved successfully for channel '{channel_name}'!")
                
                file_queue.task_done()
                
            except Exception as e:
                print(f"Error processing file: {e}")
    
    # Start file processing thread
    processor_thread = threading.Thread(target=process_file)
    processor_thread.start()
    
    current_file_info = None # (channel_name, file_name, file_size)
    current_chunks = []
    
    while True:
        try:
            # Receive data
            data, addr = sock.recvfrom(1024)
            
            # Check for DONE marker
            if data.startswith(b"DONE"):
                if current_file_info:
                    file_queue.put((current_file_info[0], current_file_info[1], current_file_info[2], current_chunks))
                    current_file_info = None
                    current_chunks = []
                continue
            
            # Check for FILE_INFO message
            if data.startswith(b"FILE_INFO|"):
                file_info_str = data.decode()
                parts = file_info_str.split('|')
                if len(parts) == 4:
                    command, received_channel_name, file_name, file_size_str = parts
                    file_size = int(file_size_str)
                    current_file_info = (received_channel_name, file_name, file_size)
                    current_chunks = []
                    
                    # If file is for this channel, print receiving message
                    if received_channel_name == channel_name:
                         print(f"\nReceiving file for channel '{channel_name}': {file_name}")
                         print(f"File size: {file_size} bytes")
                
            elif current_file_info:
                # This is file data, assume it belongs to the current file_info
                current_chunks.append(data)
                received_size = sum(len(chunk) for chunk in current_chunks)
                
                # If file is for this channel, print progress
                if current_file_info[0] == channel_name:
                    print(f"Progress for '{channel_name}': {received_size}/{current_file_info[2]} bytes", end='\r')
                    
                    # If we've received all the data for this file, queue it
                    if received_size >= current_file_info[2]:
                        file_queue.put((current_file_info[0], current_file_info[1], current_file_info[2], current_chunks))
                        current_file_info = None
                        current_chunks = []
                else:
                     # If data for a different channel's file, check if we've received enough and queue
                     if received_size >= current_file_info[2]:
                         file_queue.put((current_file_info[0], current_file_info[1], current_file_info[2], current_chunks))
                         current_file_info = None
                         current_chunks = []
            
        except socket.timeout:
            pass
        except Exception as e:
            print(f"Error receiving data: {e}")
    
    # Cleanup
    file_queue.put(None)
    processor_thread.join()
    sock.close()

if __name__ == "__main__":
    # Multicast configuration
    MULTICAST_GROUP = '224.3.29.71'
    PORT = 10000
    
    # Specific token and channel for Receiver B
    TOKEN = "channel_alpha_token"
    CHANNEL_NAME = "Channel Alpha"
    
    # The save directory can be channel-specific if desired:
    SAVE_DIR = f'received_files_{CHANNEL_NAME.replace(" ", "_")}'
    # SAVE_DIR = 'received_files' # Or keep a single directory
    
    print(f"Starting Receiver B for channel '{CHANNEL_NAME}'...")
    receive_file_multicast(MULTICAST_GROUP, PORT, TOKEN, CHANNEL_NAME, SAVE_DIR) 