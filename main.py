"""
UA Library Room Booker - Main Entry Point

A natural language application for booking library rooms at
the University of Arizona.

Usage:
    python main.py          - Launch the GUI application
    python main.py --cli    - Use command-line interface
"""

import sys
import argparse
from dotenv import load_dotenv

from parser import NaturalLanguageParser
from browser import BookingAutomation
from gui import BookingApp
from config import AppConfig
from telegram_bot import run_telegram_bot


def run_cli():
    """Run the command-line interface."""
    parser = NaturalLanguageParser()

    print("=" * 50)
    print("UA Library Room Booker - Command Line Interface")
    print("=" * 50)
    print("\nEnter your booking request in natural language.")
    print("Examples:")
    print("  - 'a room for 4 people on Tuesday around 4pm'")
    print("  - 'quiet study space for tomorrow morning'")
    print("  - 'group room for 6 on Friday at 2pm'")
    print("\nType 'quit' to exit.\n")

    while True:
        try:
            user_input = input("\nYour request: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            if not user_input:
                print("Please enter a booking request.")
                continue

            # Parse the request
            print("\nParsing your request...")
            request = parser.parse(user_input)

            print("\nInterpreted request:")
            print("-" * 40)
            print(request)
            print("-" * 40)

            # Confirm
            confirm = input("\nProceed with booking? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("Booking cancelled.")
                continue

            # Start booking
            print("\nStarting browser automation...")
            automation = BookingAutomation(headless=False, interactive_mode=True, keep_browser_open=True)

            success = automation.book_room(request)

            if success:
                print("\n" + "=" * 40)
                print("BOOKING SUCCESSFUL!")
                print("=" * 40)
            else:
                print("\nBooking could not be completed automatically.")
                print("Please check the browser window to finish manually.")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")


def run_gui():
    """Run the GUI application."""
    app = BookingApp()
    app.run()


def main():
    """Main entry point."""
    load_dotenv()
    arg_parser = argparse.ArgumentParser(
        description="UA Library Room Booker - Book library rooms using natural language"
    )
    arg_parser.add_argument(
        '--cli',
        action='store_true',
        help='Use command-line interface instead of GUI'
    )
    arg_parser.add_argument(
        '--telegram',
        action='store_true',
        help='Run Telegram booking bot'
    )

    args = arg_parser.parse_args()

    if args.telegram:
        config = AppConfig.from_env()
        run_telegram_bot(config)
    elif args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
