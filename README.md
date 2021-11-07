# Clamav-proxy
Enable scalable antivirus scanning powered by clamav!

The service comes as an endpoint you can proxy your web requests for a certain host toward.
The service will then download and scan your files before delivering the data to the client making the download request.

The scan results are stored in redis with an automatic expiry after 24 hours. If a scan result is found in redis the 
download will be immediately streamed to the client instead of being scanned.


## Configuration
To enable a proxy pass to the scan service use the following template:
`nginx.proxy.conf`
```conf
server {
    listen ${EXAMPLE_PORT};
    location / {
        proxy_pass http://clamav-scanservice:80/;
        proxy_set_header Download-From ${EXAMPLE_DOWNLOAD_FROM};
        proxy_set_header Cache-Scan ${EXAMPLE_CACHE_SCAN};
    }
}
```
The conf file can be mounted in `/etc/nginx/templates` and can be templated using env vars such as `EXAMPLE_PORT` in 
the example.

The header `Download-From` is used by the scan service to determine where to download from. For example: to download
python packages you can use `https://files.pythonhosted.org/`.

The header `Cache-Scan` is used to determine whether the scan results should be cached. You can set this to `True` for 
immutable download source like pypi. It defaults to False, not considering previous scans.
Scan results are kept for up to 24 hours.


## Underlying architecture
The service uses a python web server for incoming requests. It will then:
1. Check for an existing scan result in redis
   If there is a scan result it will:
     - Refuse the request with a 409 for infected files.
     - Stream the file in chunks to the client for
2. Download the requested file in chunks.
3. Send the downloaded file to the clamav container for scanning, which will send a scan result back
4. Store the scan result in redis.
5. 
   - If no virus was found serve the downloaded file
   - If a virus was found abort the request with a http status code 409 (conflicted resource)

<img alt="img" src="./docs/architecture.png" title="underlying architecture"/>