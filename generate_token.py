#!/usr/bin/env python3
"""
Utility script to generate secure API tokens for the YouTube Analyzer service.
"""
import secrets
import sys


def generate_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure token.
    
    Args:
        length: Length of the token in bytes (default: 32)
        
    Returns:
        str: URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def main():
    """Main function to generate and display a token."""
    if len(sys.argv) > 1:
        try:
            length = int(sys.argv[1])
        except ValueError:
            print("Error: Length must be an integer")
            sys.exit(1)
    else:
        length = 32
    
    token = generate_token(length)
    print(f"Generated secure API token (length={length}):")
    print(token)
    print("\nAdd this to your .env file:")
    print(f"API_TOKEN={token}")


if __name__ == "__main__":
    main()
