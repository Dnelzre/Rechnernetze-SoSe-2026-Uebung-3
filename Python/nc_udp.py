import socket
import sys
import threading

BUFFER_SIZE = 4096

def receiveLines(sock, stop_event):
    while not stop_event.is_set():
        try:
            data, c_address = sock.recvfrom(BUFFER_SIZE)
        except OSError:
            break

        line = data.decode('utf-8', errors='replace').rstrip()
        print(f'Message <{repr(line)}> received from client {c_address}')
        if line.lower() == 'stop':
            stop_event.set()
            break


def sendLine(sock, host, port, message):
    sock.sendto(message.encode('utf-8'), (host, port))


def chatMode(local_port):
    stop_event = threading.Event()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('0.0.0.0', local_port))

        receiver = threading.Thread(target=receiveLines, args=(sock, stop_event), daemon=True)
        receiver.start()

        print('UDP chat started.')
        print('Commands: send <ip> <port> <message> | stop')

        while not stop_event.is_set():
            try:
                line = input('> ').strip()
            except EOFError:
                stop_event.set()
                break

            if not line:
                continue

            if line.lower() == 'stop':
                stop_event.set()
                break

            if line.lower().startswith('send '):
                parts = line.split(' ', 3)
                if len(parts) < 4:
                    print('Usage: send <ip> <port> <message>')
                    continue

                host = parts[1]
                try:
                    port = int(parts[2])
                except ValueError:
                    print('Port must be an integer.')
                    continue

                message = parts[3]
                sendLine(sock, host, port, message)
                continue

            print('Unknown command. Use: send <ip> <port> <message> or stop')

        stop_event.set()


def receiveOnly(port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('0.0.0.0', port))
        while True:
            data, c_address = sock.recvfrom(BUFFER_SIZE)
            line = data.decode('utf-8', errors='replace').rstrip()
            print(f'Message <{repr(line)}> received from client {c_address}')
            if line.lower() == 'stop':
                break


def sendOnly(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for line in sys.stdin:
            line = line.rstrip()
            sock.sendto(line.encode('utf-8'), (host, port))
            if line.lower() == 'stop':
                break

def main():
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        name = sys.argv[0]
        print(f"Usage: \"{name} -l <port>\" or \"{name} <ip> <port>\" or \"{name} <local-port>\"")
        sys.exit()

    if len(sys.argv) == 2:
        chatMode(int(sys.argv[1]))
        return

    port = int(sys.argv[2])
    if sys.argv[1].lower() == '-l':
        chatMode(port)
    else:
        sendOnly(sys.argv[1],port)

if __name__ == '__main__':
    main()
