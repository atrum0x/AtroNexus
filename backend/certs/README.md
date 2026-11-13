# Extra CA certificates

Every `*.crt` file here (PEM format) is added to the Docker image's system trust store.

## Why

Some IFS servers send only their own certificate and leave out the intermediate that signed it. Windows and browsers download the missing intermediate on their own, so the site looks fine there. Linux doesn't, and IFS calls fail with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`.

## What's here

- `sectigo-public-server-auth-ca-dv-r36.crt`: issuer of the `uat-dssifs.lk` certificate (DSS UAT). Downloaded from the address in that certificate (`http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt`) and checked against its signature. Valid until 2036-03-21.

## Adding one

When a new IFS server fails this way, get its issuer certificate (the "CA Issuers" URL in the server certificate), convert it to PEM if needed, save it here as `<name>.crt`, and rebuild the backend image.

The proper fix is on the IFS server: configure it to send the full chain. Then nothing here is needed for that server.
