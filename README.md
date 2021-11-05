# Clamav-proxy
Enable scalable antivirus scanning powered by clamav!

The service comes as an endpoint you can proxy your web requests for a certain host toward.
The service will then download and scan your files before delivering the data to the client making the download request.

The scan results are stored in redis with an automatic expiry after 24 hours. If a scan result is found in redis the 
download will be immediately streamed to the client instead of being scanned.


## Underlying architecture
