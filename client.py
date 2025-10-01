import socket
import json

# Serveriň IP adresini we portyny tanat
SERVER_IP = "192.168.55.69"  # Birinji kompýuteriň IP adresini giriziň
SERVER_PORT = 80

def send_notification_to_server(notification_message: str):
    """Servere duýduryş maglumatlaryny ugradar"""
    try:
        # Servere baglanmak üçin soket açmak
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((SERVER_IP, SERVER_PORT))  # Servere baglanýar
            s.sendall(notification_message.encode('utf-8'))  # Duýduryşy ugradýar
            print(f"Client: Servere maglumat ugradylady: {notification_message}")
    except Exception as e:
        print(f"Client: Ýalňyşlyk ýüze çykdy - {e}")

def listen_for_notifications():
    """Serverden duýduryş kabul etmek"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Servere baglanyş
            s.connect((SERVER_IP, SERVER_PORT))
            print(f"Client: Server bilen baglandy! ({SERVER_IP}:{SERVER_PORT})")

            while True:
                # Serverden maglumat almak
                data = s.recv(1024)  # Max. 1024 bayt almak
                if not data:
                    break

                # Maglumaty çöz we görkeziň
                message = data.decode('utf-8')
                print(f"Client: Serverden alnan duýduryş:\n{message}")
                
        except Exception as e:
            print(f"Client: Server bilen baglanyşykda ýalňyşlyk - {e}")

if __name__ == "__main__":
    # Duýduryş goýup, ugratmak
    notification_message = "Apple gözleg edildi. Gözleg wagty: 2025-09-29 14:25:10"
    send_notification_to_server(notification_message)
    
    # Serverden duýduryş almak
    listen_for_notifications()
