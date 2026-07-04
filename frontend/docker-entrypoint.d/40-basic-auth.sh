#!/bin/sh
# Generate the nginx basic-auth file from env at container start, so credentials
# live only in .env and never in the image or git.
set -e

: "${BASIC_AUTH_USER:=builder}"
: "${BASIC_AUTH_PASS:=change_me_local_dev}"

htpasswd -bc /etc/nginx/.htpasswd "$BASIC_AUTH_USER" "$BASIC_AUTH_PASS"
