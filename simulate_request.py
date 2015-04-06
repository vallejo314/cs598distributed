"""
Main module for the simulation of the secret-sharing, multiple KMS based data request.
"""

import multiprocessing
import select
import socket
from secretsharing import PlaintextToHexSecretSharer

# The key that we are splitting.
KEY = 'correct horse battery staple'
# The number of splits required to recompute the secret.
M_NUM = 3
# The number of total KMS instances we are running.
KMS_NUM = 10

TCP_IP = '127.0.0.1'
BUFFER_SIZE = 1024
# Base port for NameNode to listen for the User.
NAMENODE_USER_LISTEN_PORT = 5200
# Base port for KMS to listen for the NameNode
KMS_NAMENODE_LISTEN_PORT = 5400

# Code for the User
def make_request(destination_port):
	send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	send_socket.connect((TCP_IP, destination_port))
	send_socket.send('pls')

	response = send_socket.recv(BUFFER_SIZE)
	send_socket.close()

	print "Response is: %s" % (response)
	print "Actual is: %s" % (KEY)

# Code for the NameNode
def listen_for_user_request(user_listen_port, kms_ports):
	
	# First set up the listening ports.
	user_listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	user_listen_socket.bind((TCP_IP, user_listen_port))
	user_listen_socket.listen(1)

	# Get the user request
	user_conn, user_addr = user_listen_socket.accept()
	request = user_conn.recv(BUFFER_SIZE)

	print 'User request received.'

	# Ask the KMS for key shares
	kms_sockets = []
	for kms_port in kms_ports:
		kms_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		kms_socket.connect((TCP_IP, kms_port))
		kms_socket.send('pls')
		kms_sockets.append(kms_socket)

	# Wait for a kms socket to respond
	received_shares = []
	while len(received_shares) < M_NUM:
		ready, _, _ = select.select(kms_sockets, [], [])
		for kms_socket in ready:
			if len(received_shares) >= M_NUM:
				break
			received_shares.append(kms_socket.recv(BUFFER_SIZE))

	# Reconstruct the key and send it back to the user
	key = PlaintextToHexSecretSharer.recover_secret(received_shares)
	print 'Key reconstructed.'
	user_conn.send(key)
	
	# Cleanup.
	user_conn.close()
	for kms_socket in kms_sockets:
		kms_socket.close()

# Code for the KMS
def listen_for_name_node_request(listen_port, share):
	# First set up the listening port
	listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	listen_socket.bind((TCP_IP, listen_port))
	listen_socket.listen(1)

	node_conn, node_addr = listen_socket.accept()
	request = node_conn.recv(BUFFER_SIZE)
	node_conn.send(share)
	node_conn.close()

class SetupProcesses:
    """
    Handles the creation of the User, NameNode, and KMS processes.
    Splits the key and distributes it among the KMS processes.
    """

    def __init__(self):
        # The list of the shares.
        self.shares = PlaintextToHexSecretSharer.split_secret(KEY, M_NUM, KMS_NUM)
        self.kms_ports = [KMS_NAMENODE_LISTEN_PORT + i for i in range(KMS_NUM)]

        # Spawn the NameNode.
        name_node = multiprocessing.Process(
            target = listen_for_user_request,
            args = (NAMENODE_USER_LISTEN_PORT,
                    self.kms_ports))
        name_node.start()

        # Spawn the KMS.
        for i in range(len(self.shares)):
            kms = multiprocessing.Process(
                target = listen_for_name_node_request,
                args = (self.kms_ports[i], self.shares[i]))
            kms.start()

        # Spawn the User.
        user = multiprocessing.Process(
            target = make_request,
            args = (NAMENODE_USER_LISTEN_PORT,))
        user.start()


# Encrypt the data and set up the 
if __name__ == '__main__':
    SetupProcesses()