# meta-debian


### No module named '_ssl'.

https://www.bytezonex.com/archives/sVZtKwY7.html
https://stackoverflow.com/questions/62830862/how-to-install-python3-8-on-debian-10
``` 
wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz
tar -zxvf openssl-1.1.1w.tar.gz
cd openssl-1.1.1w
./config --prefix=/usr/local/openssl shared zlib
make -j16&& make install
```

```
curl -O https://www.python.org/ftp/python/3.8.2/Python-3.8.2.tar.xz
tar -xf Python-3.8.2.tar.xz
cd Python-3.8.2
./configure --with-openssl=/usr/local/openssl --enable-optimizations --enable-loadable-sqlite-extensions
make -j16&&make install
python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"
```


### ModuleNotFoundError: No module named 'debian'

```
python3 -m pip install python-debian
```