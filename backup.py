# Include proper print functions
from __future__ import print_function

# Import ConfigParser
import ConfigParser

# Import standard libs
import sys, os.path, webbrowser, argparse, logging, logging.handlers

# Assure that all operations involving files only allow user readable
os.umask(0077)

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
    filename = os.path.dirname(os.path.realpath(__file__)) + "/.backup_settings"
    
    dropbox = {}
    
    config = ConfigParser.RawConfigParser()
    
    # TODO: Add logging to Config class
    
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
        
        fields = {'app_key', 'app_secret', 'access_type', 'sitename', 'aes_pass', 'at_key', 'at_sec'}
        
        for field in fields:
            logger.debug("Getting config option: " + field)
            try:
                self.get(field)
            except ConfigParser.NoOptionError:
                logger.error("Option (" + field + ") not in config file.")
                # TODO: Add option detection and correction (default options)
                raise SystemExit
        
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
    
    global logger
    
    def __init__(self):
        self.cnf = Config()
        
    def auth(self, setup = False):
        if not(self.cnf.available()) or setup:
            
            logger.info("Running setup...")
            
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
            
            self.cnf.dropbox['aes_pass'].replace(" ", "")
            
            self.sess = session.DropboxSession(self.cnf.dropbox['app_key'], self.cnf.dropbox['app_secret'], self.cnf.dropbox['access_type'])
            
            try:
                request_token = self.sess.obtain_request_token()
            except rest.ErrorResponse:
                logger.error("Invalid applications credentials.")
                raise SystemExit
            except rest.RESTSocketError:
                logger.error("Cannot connect to Dropbox Service.")
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
            except rest.ErrorResponse as e:
                logger.error("User did not allow access to application, Token is disabled or invalid.")
                raise SystemExit
            except rest.RESTSocketError:
                logger.error("Cannot connect to Dropbox Service.")
                raise SystemExit
            
            self.cnf.dropbox['at_key'] = access_token.key
            self.cnf.dropbox['at_sec'] = access_token.secret
            
            self.cnf.save()
            
        else:
            
            logger.debug("Loaded configuration.")
            
            self.sess = session.DropboxSession(self.cnf.dropbox['app_key'], self.cnf.dropbox['app_secret'], self.cnf.dropbox['access_type'])
            self.sess.set_token(self.cnf.dropbox['at_key'],self.cnf.dropbox['at_sec'])
            
        self.client = client.DropboxClient(self.sess)
        
        logger.debug("Authenticated.")
    
    def upload(self, filePath):
        size = os.path.getsize(filePath)
        logger.info("Uploading: " + filePath + " size: " + str(size/1048576) + " MB")
        
        uploader = self.client.get_chunked_uploader(open(filePath, 'rb'), size)
        while uploader.offset < size:
            logger.debug("Uploading chunk...")
            upload = uploader.upload_chunked()
            logger.debug(" ---> " + str(uploader.offset/1048576) + " MB uploaded")
        
        if DropboxBackup.DEBUG: print()

        uploader.finish("/" + self.cnf.dropbox['sitename'] + "/" + os.path.basename(os.path.normpath(filePath)), True)
        
        logger.info("Upload finished.")
    
    def encryptFile(self, in_filename, out_filename=None, chunksize=64*1024):
        logger.info("Encrypting: " + in_filename)
        
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
        
        logger.info("Encryption finished.")
                    
    def decryptFile(self, data, out_filename=None, chunksize=24*1024):
        in_filename = data[0]
        logger.info("Decrypting :" + in_filename)
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
        
        logger.info("Decryption finished.")
                
    def archive(self, backupDirectory):
        logger.info("ARCHIVE: Running archival process of: " + backupDirectory + '.')
        if os.path.exists(backupDirectory):
            self.backupDirectory = backupDirectory
        elif backupDirectory != 'decrypt':
            logger.error("Cannot complete archival of: " + backupDirectory + ", does not refer to a directory on the machine.")
            raise SystemExit
        
        logger.info("ARCHIVE: Tarring directory...")
        basename = os.path.basename(os.path.normpath(self.backupDirectory))
        tar = tarfile.open(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2" ,"w:bz2")
        tar.add(self.backupDirectory, arcname=basename+'_backup')
        tar.close()
        logger.info("ARCHIVE: Tarring finished.")
        
        self.encryptFile(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2")
        
        logger.info("ARCHIVE: Deleting unencrypted tar.")
        os.remove(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2")
        
        self.upload(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2.enc")
        
        logger.info("ARCHIVE: Deleting encrypted tar.")
        os.remove(DropboxBackup.BACKUP_TEMP + "/" + basename + ".tar.bz2.enc")
    
    def search(self, path, query = ''):
        logger.info('Running Dropbox search: query = ' + query + ' path = ' + path + '.')
        
        try:
            search_results = self.client.search("/" + self.cnf.dropbox['sitename'] + "/" + path, query)
        except rest.ErrorResponse as e:
            logger.error("Dropbox error: " + e)
        
        return search_results
        
    
    def delete_old(self, daysOld):
        pass

## ARGUMENT PARSING
parser = argparse.ArgumentParser(description='Encrypts and uploads to dropbox a specified folder. Also provides decryption functionality.')

# Add arguments
parser.add_argument('--setup', action='store_true', help="Sets up the dropbox connection.")
parser.add_argument('--backup', action='store', help="Backs up encrypted folder to dropbox.")
parser.add_argument('--decrypt', nargs=2, metavar=('FILE', 'PASSWORD'), action='store', help="Decrypt a file")
parser.add_argument('--search', action='store', help="Finds files matching string and prints them from the app dir.")
parser.add_argument('--debug', '-d', action='store_true', help="Enables the debug mode")

# Parse arguments
args = parser.parse_args()

# Check if there is no options selected
if args.setup == False and args.backup == None and args.decrypt == None and args.search == None:
    parser.print_help()
    raise SystemExit

## LOGGING
# Set up logger object
logger = logging.getLogger('DropboxLogger')

# Set maximum log level for the logger
logger.setLevel(logging.DEBUG)

# Define the format for the logging
formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s(%(process)d): %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')    

# create file handler for saving and rotating a physical log file
fileHandler = logging.handlers.RotatingFileHandler(os.path.dirname(os.path.realpath(__file__)) + '/log_backup.txt', maxBytes=10240)

# create console handler with a higher log level
ch = logging.StreamHandler()

# Give handlers formatting
fileHandler.setFormatter(formatter)
ch.setFormatter(formatter)

# Only permit higher log levels
if args.debug:
    ch.setLevel(logging.DEBUG)
else:
    ch.setLevel(logging.ERROR)

# Add handlers
logger.addHandler(fileHandler)
logger.addHandler(ch)

# DropboxBackup object
db = DropboxBackup()

## ARGUMENT COMMAND PARSING
if args.setup:
    logger.debug("Setup option selected.")
    db.auth(args.setup)

elif args.decrypt != None and (args.decrypt[0] != None and args.decrypt[1] != None):
    logger.debug("Decrypt option selected.")
    
    if not(os.path.exists(args.decrypt[0])):
        print(args.decrypt + " does not exist.")
        raise SystemExit
    
    db.decryptFile(args.decrypt)
    
elif (args.backup != None):
    logger.debug("Backup option selected.")
    db.auth()
    db.archive(args.backup)

elif (args.search != None):
    logger.debug("Search option selected.")
    
    db.auth()
    files = db.search("",args.search)
    
    for file in files:
        print(file['path'])
logger.info("Done.")
