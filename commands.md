# BotFather Commands

## Public Commands

Paste this block into BotFather `Edit Commands`:

```text
start - Open the main menu
help - Show help and usage tips
version - Show the bot version
changelog - Show recent release notes
add - Add a new tracking number
myparcels - Show your tracked parcels
settings - Open settings
language - Change language
```

## Admin Commands

These commands are registered only for the private chats listed in `ADMIN_USER_IDS`:

```text
admin - Open the admin dashboard
stats - Show bot statistics
users - List bot users
parcels - Show recent parcels
```

## Notes

- `/skip` is only used during the add-parcel naming step and does not need to be registered in BotFather.
- `/clearname` is only used during parcel rename flow and does not need to be registered in BotFather.
