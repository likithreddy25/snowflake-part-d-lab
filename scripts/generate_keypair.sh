#!/bin/bash
# Generate RSA key pair for Snowflake key-pair authentication
# Usage: ./scripts/generate_keypair.sh <username>

if [ -z "$1" ]; then
  echo "Usage: $0 <username>"
  exit 1
fi

USERNAME=$1
KEYS_DIR="./keys"

# Create keys directory if it doesn't exist
mkdir -p "$KEYS_DIR"

# Generate private key (PKCS#8, encrypted with passphrase)
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out "$KEYS_DIR/${USERNAME}_private_key.p8" -v2 des3

# Generate public key from private key
openssl pkey -in "$KEYS_DIR/${USERNAME}_private_key.p8" -pubout -out "$KEYS_DIR/${USERNAME}_public_key.pub"

echo "✓ Key pair generated:"
echo "  Private key: $KEYS_DIR/${USERNAME}_private_key.p8"
echo "  Public key:  $KEYS_DIR/${USERNAME}_public_key.pub"
echo ""
echo "Next: Register the public key in Snowflake:"
echo "  1. Copy the contents of $KEYS_DIR/${USERNAME}_public_key.pub"
echo "  2. Run in Snowsight as ACCOUNTADMIN:"
echo "     ALTER USER $USERNAME SET RSA_PUBLIC_KEY = '<public_key_content>';"
echo ""
echo "Then set environment variables:"
echo "  export SNOWFLAKE_PRIVATE_KEY_PATH=$KEYS_DIR/${USERNAME}_private_key.p8"
echo "  export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=<passphrase_you_entered>"
