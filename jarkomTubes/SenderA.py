import socket
import struct
import time
import os
import threading
import json
import hashlib

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

class ReliableMulticastSender:
    def __init__(self, multicast_group, port):
        self.multicast_group = multicast_group
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
        self.sequence_number = 0
        self.ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ack_sock.bind(('', 0))  # Bind to any available port
        self.ack_port = self.ack_sock.getsockname()[1]
        self.ack_thread = threading.Thread(target=self._listen_for_acks)
        self.ack_thread.daemon = True
        self.ack_thread.start()
        self.pending_acks = {}
        self.max_retries = 3
        self.retry_delay = 0.1

    def _listen_for_acks(self):
        while True:
            try:
                data, addr = self.ack_sock.recvfrom(1024)
                ack_data = json.loads(data.decode())
                if ack_data['type'] == 'ACK':
                    seq_num = ack_data['sequence']
                    if seq_num in self.pending_acks:
                        del self.pending_acks[seq_num]
            except Exception as e:
                print(f"Error receiving ACK: {e}")

    def _send_with_retry(self, data, is_file=False):
        seq_num = self.sequence_number
        self.sequence_number += 1
        
        # Prepare packet
        packet = {
            'sequence': seq_num,
            'type': 'FILE' if is_file else 'TEXT',
            'data': data,
            'ack_port': self.ack_port
        }
        
        # Add checksum
        packet['checksum'] = hashlib.md5(str(packet).encode()).hexdigest()
        
        # Convert to JSON and encode
        packet_data = json.dumps(packet).encode()
        
        # Send packet with retries
        retries = 0
        while retries < self.max_retries:
            try:
                self.sock.sendto(packet_data, (self.multicast_group, self.port))
                self.pending_acks[seq_num] = time.time()
                
                # Wait for ACK
                start_time = time.time()
                while time.time() - start_time < self.retry_delay:
                    if seq_num not in self.pending_acks:
                        return True
                    time.sleep(0.01)
                
                retries += 1
                if retries < self.max_retries:
                    print(f"Retrying packet {seq_num}...")
                    time.sleep(self.retry_delay)
            except Exception as e:
                print(f"Error sending packet: {e}")
                retries += 1
        
        return False

    def send_file(self, file_path):
        try:
            # Get file size
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # Send file info
            file_info = {
                'name': file_name,
                'size': file_size
            }
            if not self._send_with_retry(file_info, True):
                print("Failed to send file info")
                return
            
            # Send file content in chunks
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(1024)
                    if not chunk:
                        break
                    if not self._send_with_retry(chunk.hex(), True):
                        print("Failed to send file chunk")
                        return
                    time.sleep(0.01)  # Small delay
            
            # Send end marker
            if not self._send_with_retry("DONE", True):
                print("Failed to send end marker")
                return
            
            print(f"File {file_name} sent successfully!")
            
        except Exception as e:
            print(f"Error sending file: {e}")

    def send_text(self, text):
        try:
            # Split text into chunks if it's too large
            chunk_size = 1024
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            
            # Send number of chunks first
            if not self._send_with_retry(str(len(chunks))):
                print("Failed to send chunk count")
                return
            
            # Send each chunk
            for i, chunk in enumerate(chunks):
                if not self._send_with_retry(chunk):
                    print(f"Failed to send chunk {i+1}/{len(chunks)}")
                    return
                time.sleep(0.01)  # Small delay
            
            print("Text message sent successfully!")
            
        except Exception as e:
            print(f"Error sending text message: {e}")

    def close(self):
        self.sock.close()
        self.ack_sock.close()

if __name__ == "__main__":
    # Multicast configuration
    MULTICAST_GROUP = '224.3.29.71'
    MULTICAST_PORT = 10000
    
    sender = ReliableMulticastSender(MULTICAST_GROUP, MULTICAST_PORT)
    
    try:
        while True:
            print("\nReliable Multicast Sender")
            print("1. Send a file")
            print("2. Send a text message")
            print("3. Exit")
            choice = input("Enter your choice (1-3): ")
            
            if choice == '1':
                file_path = input("Enter the path of the file to send: ")
                if os.path.exists(file_path):
                    print(f"Sending file...")
                    sender.send_file(file_path)
                else:
                    print("File not found!")
            elif choice == '2':
                text_message = input("Enter your text message: ")
                print(f"Sending text message...")
                sender.send_text(text_message)
            elif choice == '3':
                print("Exiting...")
                break
            else:
                print("Invalid choice!")
    finally:
        sender.close() 