import socket
import struct
import os
import threading
import queue

def receive_file_multicast(multicast_group, port, save_dir='received_files'):
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
    
    print(f"Receiver B listening on {multicast_group}:{port}")
    
    # Queue for file processing
    file_queue = queue.Queue()
    
    def process_file():
        while True:
            try:
                file_data = file_queue.get()
                if file_data is None:
                    break
                    
                file_name, file_size, data_chunks = file_data
                save_path = os.path.join(save_dir, file_name)
                
                print(f"\nProcessing file: {file_name}")
                print(f"File size: {file_size} bytes")
                
                with open(save_path, 'wb') as file:
                    for chunk in data_chunks:
                        file.write(chunk)
                
                print(f"File {file_name} saved successfully!")
                file_queue.task_done()
                
            except Exception as e:
                print(f"Error processing file: {e}")
    
    # Start file processing thread
    processor_thread = threading.Thread(target=process_file)
    processor_thread.start()
    
    current_file = None
    current_chunks = []
    
    while True:
        try:
            # Receive data
            data, addr = sock.recvfrom(1024)
            
            if data == b"DONE":
                if current_file:
                    file_queue.put((current_file[0], current_file[1], current_chunks))
                    current_file = None
                    current_chunks = []
                continue
            
            # If this is file info
            if not current_file:
                file_info = data.decode()
                file_name, file_size = file_info.split('|')
                current_file = (file_name, int(file_size))
                current_chunks = []
                print(f"\nReceiving file: {file_name}")
                print(f"File size: {file_size} bytes")
            else:
                # This is file data
                current_chunks.append(data)
                received_size = sum(len(chunk) for chunk in current_chunks)
                print(f"Progress: {received_size}/{current_file[1]} bytes", end='\r')
                
                # If we've received all the data, queue it for processing
                if received_size >= current_file[1]:
                    file_queue.put((current_file[0], current_file[1], current_chunks))
                    current_file = None
                    current_chunks = []
            
        except Exception as e:
            print(f"Error receiving file: {e}")
    
    # Cleanup
    file_queue.put(None)
    processor_thread.join()
    sock.close()

if __name__ == "__main__":
    # Multicast configuration
    MULTICAST_GROUP = '224.3.29.71'
    PORT = 10000
    
    print("Starting Receiver B...")
    receive_file_multicast(MULTICAST_GROUP, PORT) 