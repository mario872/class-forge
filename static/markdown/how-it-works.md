<!-- 
Copyright (C) 2024  James Glynn

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see https://www.gnu.org/licenses/gpl-3.0.html.
-->

## In Short
Class Forge isn't too complicated once you understand how it works. Below is a step-by-step guide as to how Class Forge Works. If you're not comfortable with how it works, then please do not use it.

(This is highly oversimpified.)

1. You login, and Class Forge logs into Sentral as you, to check if your details are correct.
2. Your details are securely assymetrically encrypted (one key encrypts, another decrypts), and the keys used to decrypt them are stored as cookies in your browser
3. Your details are saved to the server, so you don't have to login everytime you check your timetable
3. When you go to your dashboard, Class Forge pulls the cookies used to decrypt your details from the browser
4. Class Forge then logs into Sentral as you again, and scrapes various paghes including your timetable and notice and then logs out of Sentral
5. Your notices and timetable etc. are then symmetrically encrypted (one key for encryption and decryption) using the cookie saved in your browser and saved on my server
6. Your timetable and notices etc. are then opened, and decrypted using the cookie in your browser, and displayed to you on the page.