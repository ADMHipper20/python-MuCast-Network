import socket
import struct
import os
import threading
import queue
import hashlib
import sys
import time
import json

def get_unique_filename(save_dir, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    
    while os.path.exists(os.path.join(save_dir, new_filename)):
        new_filename = f"{base} ({counter}){ext}"
        counter += 1
    
    return new_filename

class ReliableMulticastReceiver:
    def __init__(self, multicast_group, port, receiver_id, save_dir='received_files'):
        self.multicast_group = multicast_group
        self.port = port
        self.receiver_id = receiver_id
        self.save_dir = save_dir
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', port))
        
        # Join multicast group
        mreq = struct.pack('4sL', socket.inet_aton(multicast_group), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # Create save directory
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        # Initialize state
        self.sequence_numbers = set()
        self.file_queue = queue.Queue()
        self.current_file_info = None
        self.current_chunks = []
        self.text_chunks = []
        self.expected_chunks = 0
        
        # Start file processing thread
        self.processor_thread = threading.Thread(target=self._process_files)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        
        print(f"Receiver {receiver_id} listening on {multicast_group}:{port}")

    def _send_ack(self, seq_num, ack_port):
        try:
            ack_data = {
                'type': 'ACK',
                'sequence': seq_num
            }
            ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ack_sock.sendto(json.dumps(ack_data).encode(), ('127.0.0.1', ack_port))
            ack_sock.close()
        except Exception as e:
            print(f"Error sending ACK: {e}")

    def _process_files(self):
        while True:
            try:
                file_data = self.file_queue.get()
                if file_data is None:
                    break
                    
                file_name, file_size, data_chunks = file_data
                
                # Get unique filename
                unique_filename = get_unique_filename(self.save_dir, file_name)
                save_path = os.path.join(self.save_dir, unique_filename)
                
                print(f"\n[Receiver {self.receiver_id}] Processing file: {unique_filename}")
                print(f"[Receiver {self.receiver_id}] File size: {file_size} bytes")
                
                with open(save_path, 'wb') as file:
                    for chunk in data_chunks:
                        file.write(bytes.fromhex(chunk))
                
                print(f"[Receiver {self.receiver_id}] File {unique_filename} saved successfully!")
                
                self.file_queue.task_done()
                
            except Exception as e:
                print(f"[Receiver {self.receiver_id}] Error processing file: {e}")

    def _handle_packet(self, packet_data, addr):
        try:
            # Parse packet
            packet = json.loads(packet_data.decode())
            seq_num = packet['sequence']
            
            # Check if we've already processed this sequence number
            if seq_num in self.sequence_numbers:
                self._send_ack(seq_num, packet['ack_port'])
                return
            
            # Verify checksum
            received_checksum = packet.pop('checksum')
            calculated_checksum = hashlib.md5(str(packet).encode()).hexdigest()
            if received_checksum != calculated_checksum:
                print(f"[Receiver {self.receiver_id}] Checksum mismatch for packet {seq_num}")
                return
            
            # Add sequence number to processed set
            self.sequence_numbers.add(seq_num)
            
            # Send ACK
            self._send_ack(seq_num, packet['ack_port'])
            
            # Handle packet based on type
            if packet['type'] == 'FILE':
                if isinstance(packet['data'], dict):  # File info
                    self.current_file_info = (packet['data']['name'], packet['data']['size'])
                    self.current_chunks = []
                elif packet['data'] == "DONE":  # End of file
                    if self.current_file_info:
                        self.file_queue.put((self.current_file_info[0], self.current_file_info[1], self.current_chunks))
                        self.current_file_info = None
                        self.current_chunks = []
                else:  # File chunk
                    if self.current_file_info:
                        self.current_chunks.append(packet['data'])
                        received_size = sum(len(bytes.fromhex(chunk)) for chunk in self.current_chunks)
                        print(f"[Receiver {self.receiver_id}] Progress: {received_size}/{self.current_file_info[1]} bytes", end='\r')
            
            elif packet['type'] == 'TEXT':
                if not self.expected_chunks:  # First packet contains chunk count
                    self.expected_chunks = int(packet['data'])
                    self.text_chunks = []
                else:  # Text chunk
                    self.text_chunks.append(packet['data'])
                    if len(self.text_chunks) == self.expected_chunks:
                        complete_text = ''.join(self.text_chunks)
                        print(f"\n[Receiver {self.receiver_id}] Text Message: {complete_text}")
                        self.text_chunks = []
                        self.expected_chunks = 0
            
        except Exception as e:
            print(f"[Receiver {self.receiver_id}] Error handling packet: {e}")

    def start(self):
        try:
            while True:
                data, addr = self.sock.recvfrom(65535)  # Increased buffer size
                self._handle_packet(data, addr)
        except Exception as e:
            print(f"[Receiver {self.receiver_id}] Error receiving data: {e}")
        finally:
            self.file_queue.put(None)
            self.processor_thread.join()
            self.sock.close()

if __name__ == "__main__":
    # Multicast configuration
    MULTICAST_GROUP = '224.3.29.71'
    PORT = 10000
    
    # Receiver identification
    RECEIVER_ID = "D"
    
    # The save directory
    SAVE_DIR = f'received_files_Receiver_{RECEIVER_ID}'
    
    print(f"Starting Receiver {RECEIVER_ID}...")
    receiver = ReliableMulticastReceiver(MULTICAST_GROUP, PORT, RECEIVER_ID, SAVE_DIR)
    receiver.start() 