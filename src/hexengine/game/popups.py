import js
import logging

LOGGER = logging.getLogger("PopupManager")

class PopupManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.popups = []

    def add_popup(self, popup):
        self.popups.append(popup)

    def remove_popup(self, popup):
        if popup in self.popups:
            self.popups.remove(popup)

    def get_all_popups(self):
        return self.popups

    def clear(self):
        for p in self.popups:
            p.delete(self.canvas)
        self.popups = []

    def create_popup(self, message, position):
        
        popup = Popup(message, position)
        logging.info(f"Creating popup with message: {message} at position: {position}")
        self.add_popup(popup)
        popup.display(self.canvas)
        return popup
    

class Popup:
    def __init__(self, message, position):
        self.message = message
        self.position = position
        self.element = None

    def display(self, canvas):
        div = js.document.createElement("div")
        div.className = "popup"
        div.innerHTML = self.message 
        div.style.left = f"{self.position[0]}px"
        div.style.top = f"{self.position[1]}px"
        canvas.appendChild(div)
        self.element = div
    
    def delete(self, canvas):
        LOGGER.info(f"Removing popup with message: {self.message}")
        canvas.removeChild(self.element)
