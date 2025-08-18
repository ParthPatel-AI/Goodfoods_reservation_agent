# Example Conversations

**User:** Book a table for 4 in Bandra this Friday at 8 pm. Vegetarian-friendly and rooftop if possible.  
**Assistant:** Great! To confirm: 4 guests, Friday (DD Mon YYYY), 20:00, Bandra, vegetarian-friendly, rooftop seating preferred. Shall I look for options under `$$` rating 4.0+?  
**(tool: recommend)**  
**Assistant:** Top picks: R012 GoodFoods Urban - Bandra (rating 4.6, rooftop, veg options). Shall I check availability at 20:00?  
**User:** Yes.  
**(tool: check_availability)**  
**Assistant:** Tables are available. May I book under your name and phone?  
**User:** Parth, +91-9XXXXXXXXX.  
**(tool: create_reservation)**  
**Assistant:** Done! Confirmation `AB12CD`. You'll get reminders 3 hours prior. Need directions or menu?

---

**User:** Change my reservation AB12CD to tomorrow 21:30 for 6 guests.  
**(tool: modify_reservation)**  
**Assistant:** Updated. See you tomorrow at 21:30, party of 6.

---

**User:** Cancel XYZ789.  
**(tool: cancel_reservation)**  
**Assistant:** Cancelled. Free until 2 hours before; otherwise a no-show fee may apply.
