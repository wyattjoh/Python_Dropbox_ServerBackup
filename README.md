=== Python Encrypted Dropbox Backup
== Usage
```
usage: backup.py [-h] [--setup] [--backup BACKUP] [--decrypt FILE PASSWORD]
                 [--search SEARCH] [--debug]

Encrypts and uploads to dropbox a specified folder. Also provides decryption
functionality.

optional arguments:
  -h, --help            show this help message and exit
  --setup               Sets up the dropbox connection.
  --backup BACKUP       Backs up encrypted folder to dropbox.
  --decrypt FILE PASSWORD
                        Decrypt a file
  --search SEARCH       Finds files matching string and prints them from the
                        app dir.
  --debug, -d           Enables the debug mode
```

== Installation
