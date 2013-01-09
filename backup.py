#!/usr/bin/env python -u
# Include proper print functions
from __future__ import print_function

# Import ConfigParser
import ConfigParser

# Import standard libs
import sys, os.path, webbrowser, argparse

# Include the Dropbox SDK libraries
from dropbox import client, rest, session

# Include crypto libs
from Crypto.Cipher import AES
from Crypto import Random
import random, struct, hashlib

# Include Tarfile
import tarfile

class Config:
    # Config File
    filename = ".backup_settings"
    
    dropbox = {}
    
    config = ConfigParser.RawConfigParser()
    
    def __init__(self):
        self.config.add_section('dropbox')
    
    def save(self):
        for key in Config.dropbox:
            self.config.set('dropbox', key, Config.dropbox[key])
        
        configfile = open(Config.filename, 'wb')
        self.config.write(configfile)
    
    def get(self, key):
        self.dropbox[key] = self.config.get('dropbox', key)
    
    def load(self):
        self.config.read(Config.filename)
        
        self.get('app_key')
        self.get('app_secret')
        self.get('access_type')
        self.get('sitename')
        self.get('aes_pass')
        self.get('at_key')
        self.get('at_sec')
        
    def printOut(self):
        for key in Config.dropbox:
            print(key, Config.dropbox[key])
    
    def available(self):
        if os.path.isfile(Config.filename):
            self.load()
            return True
        else:
            return False

class DropboxBackup:
    # Debug mode
    DEBUG = False
    
    BACKUP_TEMP = "/tmp"
    
    def __init__(self):
        self.cnf = Config()
        
    def auth(self, setup = False):
        if not(self.cnf.available()) or setup:
            
            print(" == Dropbox Application Setup ==\n")
            self.cnf.dropbox['app_key'] = raw_input(" Dropbox App Key: ")
            self.cnf.dropbox['app_secret'] = raw_input(" Dropbox App Secret: ")
            
            print("\n f: Full Dropbox Access, a: App Folder")
            db_at = raw_input(" Dropbox Access Type [f/a]: ")
            if db_at == 'f':
                self.cnf.dropbox['access_type'] = 'dropbox'
            elif db_at == 'a':
                self.cnf.dropbox['access_type'] = 'app_folder'
            else:
                print(" Invalid option: ", db_at)
                self.auth(True)
            
            self.cnf.dropbox['sitename'] = raw_input(" Sitename: ")
            
            print(" DO NOT LOSE THIS PASSWORD, REQUIRED TO RESTORE!")
            self.cnf.dropbox['aes_pass'] = raw_input(" AES PASS: ")
            
            self.sess = session.DropboxSession(self.cnf.dropbox['app_key'], self.cnf.dropbox['app_secret'], self.cnf.dropbox['access_type'])
            
            try:
                request_token = self.sess.obtain_request_token()
            except:
                print(" Check application configuration, invalid credientials.")
                raise SystemExit
            
            url = self.sess.build_authorize_url(request_token)
            
            # Make the user sign in and authorize this token
            try:
                browser = webbrowser.get('macosx')
                
                print("\n Please click allow in the window that opens, then press [ENTER]")
                browser.open_new_tab(url)
            except:
                 print("\n Please visit this website and press the 'Allow' button, then hit [Enter]")
                 print(" --> ", url)
            
            raw_input()
            
            # This will fail if the user didn't visit the above URL and hit 'Allow'
            try:
                access_token = self.sess.obtain_access_token(request_token)
            except:
                print("\n Request for tokens DENIED.")
                raise SystemExit
            
            self.cnf.dropbox['at_key'] = access_token.key
            self.cnf.dropbox['at_sec'] = access_token.secret
            
            self.cnf.save()
            
        else:
            self.sess = session.DropboxSession(self.cnf.dropbox['app_key'], self.cnf.dropbox['app_secret'], self.cnf.dropbox['access_type'])
            self.sess.set_token(self.cnf.dropbox['at_key'],self.cnf.dropbox['at_sec'])
            
        self.client = client.DropboxClient(self.sess)
        
        if DropboxBackup.DEBUG: print("Authenticated.")
    
    def upload(self, filePath):
        if DropboxBackup.DEBUG: print("Now uploading: ", filePath, ">> ", end='')
        size = os.path.getsize(filePath)
        uploader = self.client.get_chunked_uploader(open(filePath, 'rb'), size)
        while uploader.offset < size:
            upload = uploader.upload_chunked()
            if DropboxBackup.DEBUG: print(".", end='')
        
        if DropboxBackup.DEBUG: print()

        uploader.finish("/" + self.cnf.dropbox['sitename'] + "/" + os.path.basename(filePath), True)
    
    def encryptFile(self, in_filename, out_filename=None, chunksize=64*1024):
        if DropboxBackup.DEBUG: print("Encrypting :", in_filename)
        
        key = hashlib.sha256(self.cnf.dropbox['aes_pass']).digest()
        
        if not out_filename:
            out_filename = in_filename + '.enc'

        iv = ''.join(chr(random.randint(0, 0xFF)) for i in range(16))
        encryptor = AES.new(key, AES.MODE_CBC, iv)
        filesize = os.path.getsize(in_filename)

        with open(in_filename, 'rb') as infile:
            with open(out_filename, 'wb') as outfile:
                outfile.write(struct.pack('<Q', filesize))
                outfile.write(iv)

                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    elif len(chunk) % 16 != 0:
                        chunk += ' ' * (16 - len(chunk) % 16)

                    outfile.write(encryptor.encrypt(chunk))
                    
    def decryptFile(self, data, out_filename=None, chunksize=24*1024):
        if DropboxBackup.DEBUG: print("Decrypting :", in_filename)
        in_filename = data[0]
        key = hashlib.sha256(data[1]).digest()
        
        if not out_filename:
            out_filename = os.path.splitext(in_filename)[0]

        with open(in_filename, 'rb') as infile:
            origsize = struct.unpack('<Q', infile.read(struct.calcsize('Q')))[0]
            iv = infile.read(16)
            decryptor = AES.new(key, AES.MODE_CBC, iv)

            with open(out_filename, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    outfile.write(decryptor.decrypt(chunk))

                outfile.truncate(origsize)
                
    def archive(self, backupDirectory):
        if os.path.exists(backupDirectory):
            self.backupDirectory = backupDirectory
        elif backupDirectory != 'decrypt':
            print(backupDirectory + " does not refer to a directory on the machine.")
            raise SystemExit
        
        basename = os.path.basename(self.backupDirectory)
        tar = tarfile.open(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2" ,"w:bz2")
        tar.add(self.backupDirectory)
        tar.close()
        
        self.encryptFile(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2")
        
        os.remove(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2")
        
        self.upload(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2.enc")
        
        os.remove(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2.enc")
    
    def search(self, path, query = ''):
        return self.client.search("/" + self.cnf.dropbox['sitename'] + "/" + path, query)
        
    
    def delete_old(self, daysOld):
        pass
    
parser = argparse.ArgumentParser(description='Encrypts and uploads to dropbox a specified folder. Also provides decryption functionality.')

parser.add_argument('--setup', action='store_true', help="Sets up the dropbox connection.")
parser.add_argument('--backup', action='store', help="Backs up encrypted folder to dropbox.")
parser.add_argument('--decrypt', nargs=2, metavar=('FILE', 'PASSWORD'), action='store', help="Decrypt a file")
parser.add_argument('--search', action='store', help="Finds files matching string and prints them from the app dir.")

args = parser.parse_args()

if args.setup == False and args.backup == None and args.decrypt[0] == None and args.search == None:
    parser.print_help()
    raise SystemExit

db = DropboxBackup()

if args.setup:
    db.auth(args.setup)

elif (args.decrypt[0] != None and args.decrypt[1] != None):
    
    if not(os.path.exists(args.decrypt[0])):
        print(args.decrypt + " does not exist.")
        raise SystemExit
    
    db.decryptFile(args.decrypt)
    
elif (args.backup != None):
    db.auth()
    db.archive(args.backup)

elif (args.search != None):
    db.auth()
    files = db.search("",args.search)
    
    for file in files:
        print(file['path'])
