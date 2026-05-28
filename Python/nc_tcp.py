import socket
import sys
import threading

BUFFER_SIZE = 4096
clients = {}
clients_lock = threading.Lock()


def receive_lines(sock, stop_event):
    with sock.makefile('r', encoding='utf-8', newline='') as reader:
        while not stop_event.is_set():
            line = reader.readline()
            if not line:
                stop_event.set()
                break

            print(line.rstrip())


def send_line(sock, line):
    sock.sendall((line + '\n').encode('utf-8'))


def send_line_locked(client_connection, line):
    with client_connection['lock']:
        client_connection['socket'].sendall((line + '\n').encode('utf-8'))


def active_client_names():
    with clients_lock:
        return sorted(clients.keys())


def send_client_list(client_connection):
    names = active_client_names()
    if names:
        send_line_locked(client_connection, 'CLIENTS: ' + ', '.join(names))
    else:
        send_line_locked(client_connection, 'CLIENTS: keine aktiven Clients')


def register_client(name, client_connection):
    with clients_lock:
        if name in clients:
            return False
        clients[name] = client_connection
    client_connection['name'] = name
    return True


def unregister_client(client_connection):
    name = client_connection.get('name')
    if not name:
        return

    with clients_lock:
        if clients.get(name) is client_connection:
            del clients[name]


def drop_client(name, client_connection):
    with clients_lock:
        if clients.get(name) is client_connection:
            del clients[name]


def handle_send_command(sender_name, line, client_connection):
    parts = line.split(' ', 2)
    if len(parts) < 3:
        send_line_locked(client_connection, 'ERROR: usage send <Empfängername> <Nachricht>')
        return

    recipient_name = parts[1].strip()
    message = parts[2].strip()

    if not recipient_name or not message:
        send_line_locked(client_connection, 'ERROR: usage send <Empfängername> <Nachricht>')
        return

    with clients_lock:
        recipient_connection = clients.get(recipient_name)

    if recipient_connection is None:
        send_line_locked(client_connection, f'ERROR: client "{recipient_name}" not found')
        return

    try:
        send_line_locked(recipient_connection, f'FROM {sender_name}: {message}')
    except OSError:
        drop_client(recipient_name, recipient_connection)
        send_line_locked(client_connection, f'ERROR: client "{recipient_name}" is not reachable')
        return

    try:
        send_line_locked(client_connection, f'SENT to {recipient_name}')
    except OSError:
        return


def server(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_sock:
        s_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s_sock.bind(('0.0.0.0', port))
        s_sock.listen()
        print(f'TCP chat server listening on port {port}')

        while True:
            c_sock, c_address = s_sock.accept()
            t = threading.Thread(target=serve_client, args=(c_sock, c_address), daemon=True)
            t.start()


def serve_client(c_sock, c_address):
    client_connection = {'socket': c_sock, 'lock': threading.Lock(), 'name': None}
    try:
        with c_sock.makefile('r', encoding='utf-8', newline='') as reader:
            send_line_locked(client_connection, 'Please register with: register <name>')

            while True:
                line = reader.readline()
                if not line:
                    break

                line = line.rstrip('\r\n')
                if not line:
                    continue

                if client_connection['name'] is None:
                    if not line.lower().startswith('register '):
                        send_line_locked(client_connection, 'ERROR: please register first using: register <name>')
                        continue

                    name = line.split(' ', 1)[1].strip()
                    if not name:
                        send_line_locked(client_connection, 'ERROR: name must not be empty')
                        continue

                    if not register_client(name, client_connection):
                        send_line_locked(client_connection, f'ERROR: name "{name}" is already in use')
                        continue

                    print(f'Client registered: {name} from {c_address}')
                    send_line_locked(client_connection, f'Welcome {name}!')
                    send_line_locked(client_connection, 'Commands: send <Empfängername> <Nachricht> | clients | quit')
                    send_client_list(client_connection)
                    continue

                lower_line = line.lower()
                if lower_line == 'clients':
                    send_client_list(client_connection)
                elif lower_line.startswith('send '):
                    handle_send_command(client_connection['name'], line, client_connection)
                elif lower_line in ('quit', 'exit', 'stop'):
                    send_line_locked(client_connection, 'BYE')
                    break
                elif lower_line.startswith('register '):
                    send_line_locked(client_connection, 'ERROR: already registered')
                else:
                    send_line_locked(client_connection, 'ERROR: unknown command')
    finally:
        unregister_client(client_connection)
        c_sock.close()
        if client_connection['name'] is not None:
            print(f'Client disconnected: {client_connection["name"]}')
        else:
            print(f'Unregistered client disconnected from {c_address}')


def chat_client(host, port, name=None):
    stop_event = threading.Event()

    with socket.create_connection((host, port)) as c_sock:
        receiver = threading.Thread(target=receive_lines, args=(c_sock, stop_event), daemon=True)
        receiver.start()

        if name is None:
            name = input('Registrierungsname: ').strip()

        if not name:
            print('Kein Name angegeben.')
            return

        send_line(c_sock, f'register {name}')

        print('TCP chat started.')
        print('Commands: send <Empfängername> <Nachricht> | clients | quit')

        while not stop_event.is_set():
            try:
                line = input('> ').rstrip()
            except EOFError:
                stop_event.set()
                break

            if not line:
                continue

            if line.lower() in ('/quit', 'quit', 'exit'):
                stop_event.set()
                break

            send_line(c_sock, line)

        stop_event.set()

def main():
    if len(sys.argv) not in (3, 4):
        name = sys.argv[0]
        print(f"Usage: \"{name} -l <port>\" or \"{name} <ip> <port> [name]\"")
        sys.exit()

    if sys.argv[1].lower() == '-l':
        server(int(sys.argv[2]))
        return

    host = sys.argv[1]
    port = int(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) == 4 else None
    chat_client(host, port, name)

if __name__ == '__main__':
    main()
