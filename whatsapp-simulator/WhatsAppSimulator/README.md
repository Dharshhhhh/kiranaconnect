# WhatsApp Simulator

Extract the folder and double-click Start-WhatsApp.cmd on Windows with Python 3.12 installed. The prebuilt UI and server use no external services. Open http://127.0.0.1:8090 for the customer and click Shop inbox for the other side. Send a list or photo and reply from the shop tab. SQLite stores local messages and images. This is a single-laptop simulation using the demo customer Meena. The standalone shop view is available to anyone using that laptop.

## Connect KiranaConnect later

1. Start your latest KiranaConnect Business on port 8000.
2. Change mode in connection.json from standalone to connected. Keep kiranaconnect_url pointed to the running backend.
3. Stop and restart the simulator, refresh the customer tab, then send a new message. Shop inbox opens the owner dashboard. Orders, screenshot processing, owner authentication and Kirana AI are provided by KiranaConnect.
4. A sample order is Rice 5 kg, Tea 1 pack. Standalone history stays in demo.sqlite3. Only newly sent connected messages reach KiranaConnect. To run offline again switch mode back and restart.

This simulator does not contact Meta or send messages to phone numbers. For development, frontend source is in src, server.py contains the local API and customer-route proxy, and npm ci followed by npm run build rebuilds dist.

## Kirana AI inside chats
Select Kirana AI in the chats list (use the Kirana AI button on narrow screens). In standalone mode the built-in offline helper explains ordering and retrieves recent chat messages. In connected mode customers can also ask for current catalog prices. For store tools, use Shop inbox, sign in at the configured KiranaConnect address and open Kirana AI in the simulator's shop tab. Use 127.0.0.1 for both apps so the browser supplies the owner's session cookie. Owner requests use the backend's configured offline, Sarvam or Gemini routing. Stock-changing proposals require confirmation. Owner data requires an authenticated backend session. Keep any existing connection.json and demo.sqlite3 when updating.

### Connect without editing JSON
Start KiranaConnect on port 8000. Stop an existing simulator on port 8090. Double-click Connect-to-Kirana.cmd. It checks the required store endpoints, saves connected mode and starts the simulator. Customer → Kirana AI → "Order 5 kg Rice" → Confirm sends the request to the same store intake as the shop conversation. "My order status" reads recorded reservations and fulfilments. The conversation with the shop retains review messages and image job states.
