
# use this script to mount a storage account to the linux file system 


sudo mkdir /mnt/dacoursedatashare
if [ ! -d "/etc/smbcredentials" ]; then
sudo mkdir /etc/smbcredentials
fi
if [ ! -f "/etc/smbcredentials/dacoursedatastorage.cred" ]; then
    sudo bash -c 'echo "username=dacoursedatastorage" >> /etc/smbcredentials/dacoursedatastorage.cred'
    sudo bash -c 'echo "password=2OcNMeIe6dzLJstmbqtTWEGXKdnZyxNxI0Yhsk3/befIw0yT6fa9526Ppmbi7UvBivTOj4qFta2XxkmTBiHwFw==" >> /etc/smbcredentials/dacoursedatastorage.cred'
fi
sudo chmod 600 /etc/smbcredentials/dacoursedatastorage.cred

sudo bash -c 'echo "//dacoursedatastorage.file.core.windows.net/dacoursedatashare /mnt/dacoursedatashare cifs nofail,credentials=/etc/smbcredentials/dacoursedatastorage.cred,dir_mode=0777,file_mode=0777,serverino,nosharesock,actimeo=30" >> /etc/fstab'
sudo mount -t cifs //dacoursedatastorage.file.core.windows.net/dacoursedatashare /mnt/dacoursedatashare -o credentials=/etc/smbcredentials/dacoursedatastorage.cred,dir_mode=0777,file_mode=0777,serverino,nosharesock,actimeo=30

