# AxionX iOS — TestFlight Build Notes

**Version:** 1.0 (Build 1)  
**Date:** March 2026  
**Platform:** iPhone only, iOS 16+, Portrait

---

## What is this app?

AxionX is a field operations management app for repossession and asset recovery agents. This
TestFlight build is a native iOS wrapper around the AxionX mobile web platform at
`https://www.axionx.com.au/m/`. All job data, scheduling, and workflow logic runs on
the AxionX backend — the iOS app provides native session management, GPS permission handling,
link routing, and offline error handling.

---

## TestFlight Test Plan

Please test the following flows in order:

### 1. Login
- Open the app — you should see the AxionX splash (white screen, "AxionX" text)
- The login page should load automatically
- Log in with your test credentials
- You should be redirected to Today's Schedule

### 2. Today's Schedule
- Verify the schedule list loads with correct jobs/cues for today
- Verify any urgent draft badges appear if you have unfinished updates
- Scroll to confirm smooth scrolling and no visual glitches

### 3. Open a Job
- Tap any job card
- Verify job detail page loads with: ref number, customer name, address, status
- Tap the Call button — verify it opens the Phone dialler natively
- Tap the SMS button — verify it opens Messages natively
- Tap the Navigate button — verify it opens Apple Maps

### 4. Create an Attendance Update
- From a job detail, tap the "Add Update" or AI update button
- Complete the attendance update form
- Submit the update
- Verify the draft is cleared and the note appears on the job

### 5. Map and Location Permission
- Tap the Map tab in the bottom navigation
- The app should prompt for location permission ("While Using the App")
- Grant permission — verify the map shows your location dot
- Verify job pins appear on the map
- Test the date filter pills (Today / Week / All)

### 6. Jobs List and Filters
- Tap the Jobs tab
- Verify jobs list loads
- Tap Filter — verify the filter sheet slides up from the bottom
- Change Sort By to Distance — verify the list re-orders based on your location
- Test the search bar — type a job ref or customer name

### 7. Settings
- Tap Settings tab
- Verify GPS and display preferences are visible and editable
- Change Distance Unit to Miles — tap Save Preferences
- Go to Jobs — verify distances now show in miles

### 8. Tow Operators
- In Settings, tap Tow Operators
- Verify existing operators are listed with call buttons
- Tap a call button — verify it opens the Phone dialler
- Tap + Add — fill in Company Name and Mobile — save
- Verify the new operator appears in the list

### 9. Auction Yards
- In Settings, tap Auction Yards
- Same flow as Tow Operators above

### 10. Unfinished Draft Reminder
- If you have a job with an existing incomplete draft:
  - Open that job from the Jobs list
  - Verify the "Unfinished draft" banner appears at the top
  - Verify the draft pre-populates when you enter the update builder

### 11. Offline Handling
- Turn on Airplane Mode
- Kill and reopen the app
- Verify you see the "AxionX is currently unavailable" screen with a Retry button
- Turn off Airplane Mode
- Tap Retry — verify the app reloads the login or schedule screen

### 12. Session Persistence
- Log in
- Kill the app (swipe up from the app switcher)
- Reopen the app
- Verify you land on Today's Schedule without needing to log in again

---

## Known Limitations (v1)

- App icon and launch screen use placeholder text branding (final artwork to follow)
- Push notifications not yet enabled
- Background GPS tracking is not yet enabled (foreground only)
- File/photo upload from jobs is not yet native
- iPad is not supported in this release

---

## Feedback

Please report any crashes, visual glitches, or unexpected navigation behaviour through
TestFlight feedback or direct message to the development team.
