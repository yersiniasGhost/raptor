#!/usr/bin/env python3
"""
AT Command Tool for TS-7180 Cellular Modem
Sends AT commands to the modem and prints responses

Usage:
    python3 at_tool.py "AT"
    python3 at_tool.py "AT+CSQ"
    python3 at_tool.py "AT#USBCFG?"
"""

import serial
import time
import sys
import argparse

class ATCommandTool:
    def __init__(self, device='/dev/ttymxc2', baudrate=115200, timeout=5):
        """Initialize AT command tool"""
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        
    def connect(self):
        """Connect to the modem"""
        try:
            self.serial = serial.Serial(
                port=self.device,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self.serial.flushInput()
            self.serial.flushOutput()
            print(f"✅ Connected to {self.device} at {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"❌ Error connecting to {self.device}: {e}")
            return False
    
    def send_at_command(self, command, wait_time=2):
        """Send AT command and return response"""
        if not self.serial or not self.serial.is_open:
            print("❌ Serial connection not open")
            return ""
        
        try:
            # Clear any pending data
            self.serial.flushInput()
            
            # Send command with proper line ending
            cmd_bytes = f"{command}\r\n".encode('utf-8')
            self.serial.write(cmd_bytes)
            
            print(f">>> {command}")
            
            # Wait for response
            time.sleep(wait_time)
            
            # Read all available data
            response = b""
            while self.serial.in_waiting:
                response += self.serial.read(self.serial.in_waiting)
                time.sleep(0.1)  # Small delay to catch more data
            
            # Decode response
            response_text = response.decode('utf-8', errors='ignore')
            
            # Clean up response (remove echo and extra whitespace)
            lines = response_text.split('\n')
            clean_lines = []
            
            for line in lines:
                line = line.strip('\r\n ')
                if line and line != command:  # Remove empty lines and command echo
                    clean_lines.append(line)
            
            result = '\n'.join(clean_lines)
            
            if result:
                print(f"<<< {result}")
            else:
                print("<<< (no response)")
            
            return result
            
        except Exception as e:
            print(f"❌ Error sending command: {e}")
            return ""
    
    def close(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("📱 Disconnected")

def main():
    parser = argparse.ArgumentParser(
        description='Send AT commands to cellular modem',
        epilog='Examples:\n'
               '  python3 at_tool.py "AT"\n'
               '  python3 at_tool.py "AT+CSQ"\n'
               '  python3 at_tool.py "AT#USBCFG?"\n'
               '  python3 at_tool.py "ATI" --wait 3',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('command', help='AT command to send (e.g., "AT", "AT+CSQ")')
    parser.add_argument('--device', '-d', default='/dev/ttymxc2', 
                       help='Serial device (default: /dev/ttymxc2)')
    parser.add_argument('--baudrate', '-b', type=int, default=115200,
                       help='Baud rate (default: 115200)')
    parser.add_argument('--timeout', '-t', type=float, default=5,
                       help='Serial timeout in seconds (default: 5)')
    parser.add_argument('--wait', '-w', type=float, default=2,
                       help='Wait time for response in seconds (default: 2)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive mode - keep connection open')
    
    args = parser.parse_args()
    
    # Create AT tool
    at_tool = ATCommandTool(args.device, args.baudrate, args.timeout)
    
    # Connect to modem
    if not at_tool.connect():
        sys.exit(1)
    
    try:
        if args.interactive:
            print("\n🔄 Interactive mode - type 'quit' or 'exit' to stop")
            print("Enter AT commands (without quotes):")
            
            while True:
                try:
                    command = input("\nAT> ").strip()
                    if command.lower() in ['quit', 'exit', 'q']:
                        break
                    if command:
                        at_tool.send_at_command(command, args.wait)
                except KeyboardInterrupt:
                    print("\n\n👋 Exiting...")
                    break
        else:
            # Single command mode
            at_tool.send_at_command(args.command, args.wait)
    
    finally:
        at_tool.close()

if __name__ == "__main__":
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        print("AT Command Tool for TS-7180 Cellular Modem")
        print("=" * 50)
        print("\nQuick usage:")
        print('  python3 at_tool.py "AT"')
        print('  python3 at_tool.py "AT+CSQ"')  
        print('  python3 at_tool.py "AT#USBCFG?"')
        print("\nInteractive mode:")
        print('  python3 at_tool.py --interactive "AT"')
        print("\nFor full help:")
        print('  python3 at_tool.py --help')
        sys.exit(0)
    
    main()
