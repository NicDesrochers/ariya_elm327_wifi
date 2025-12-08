#!/usr/bin/python3
import socket
import time

IP = "192.168.23.154"   # adresse IP du module
PORT = 35000           # port TCP du module

def send(sock, cmd):
    """Envoie une commande AT et retourne la réponse brute."""
    sock.send((cmd + "\r").encode())
    time.sleep(0.3)
    return sock.recv(4096).decode(errors="ignore")

def main():
    try:
        # Connexion TCP au module
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((IP, PORT))

        # Séquence d'init basique
        print(send(sock, "ATZ"))     # reset
        print(send(sock, "ATE0"))    # echo off
        print(send(sock, "ATL0"))    # linefeeds off
        print(send(sock, "ATS0"))    # spaces off

        # Désactiver le power saving : écrire 7A dans PP0E
        print(send(sock, "ATPP0ESV7A"))

        # Sauvegarder la config (appliquée après power cycle)
        print(send(sock, "ATPP0EON"))

        sock.close()
        print("Configuration envoyée avec succès.")

    except Exception as e:
        print("Erreur:", e)

if __name__ == "__main__":
    main()
