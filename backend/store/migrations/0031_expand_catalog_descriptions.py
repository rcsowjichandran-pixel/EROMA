from django.db import migrations


ROOM_NOTES = {
    "2-Seater Sofas": "Use it as the main seat in a smaller room or pair it with an accent chair for a conversation area. Check the overall width against the wall and leave room for a side table or a clear walkway.",
    "3-Seater Sofas": "Arrange it opposite a media unit or alongside an armchair to create a place to sit together. Leave enough space between the seat and a coffee table to move through the room comfortably.",
    "L-Shaped Sofas": "The corner layout can define a seating area in an open room. Before ordering, check which side the longer section sits on and whether it leaves a clear path past doors and other furniture.",
    "Modular Sofas": "Start by mapping the seating area and deciding where people will enter and move through it. Check the configuration shown for this model and measure the space it will occupy before ordering.",
    "Sofa Beds": "This type of piece is useful in a guest room or a living area that needs to serve more than one purpose. Measure the floor area in front of the sofa in its open position as well as its footprint when closed.",
    "Accent Chairs": "Set it beside a window or use it to balance a sofa arrangement. A small side table or floor lamp can give the chair a clear purpose without crowding the surrounding space.",
    "Lounge Chairs": "For a reading spot, place it near natural light with a lamp and a small table within reach. Check the space around the chair if you plan to add a footrest.",
    "Recliner Chairs": "Allow room behind and in front of the chair for its full reclining position. Check how the chair will fit beside a wall, side table, or main walking route before choosing its position.",
    "Dining Chairs": "Compare the seat height with your table height and leave enough room to pull the chair out. If you are adding it to an existing set, check its width against the available space between the table legs.",
    "Rocking Chairs": "Place it where there is clear space in front and behind for the rocking motion. A reading lamp and small table set to one side can make a quiet corner more useful.",
    "Bar Stools": "Measure from the floor to the underside of your counter or island before choosing a stool. Allow space between seats so people can sit down and get up without bumping into the next stool.",
    "Bedroom Benches": "A bench can be useful for putting on shoes or setting down a bag during the day. At the foot of a bed, keep a clear route past the bench and check that it leaves enough room for wardrobe doors to open.",
    "Bedside Tables": "Compare its height with the top of your mattress so items are easy to reach. Allow space for a lamp or charging cable, and check the width available between the bed and the nearest wall or wardrobe.",
    "Bookshelves": "Group books by size and leave a little open space around objects you want to display. Check the room height, floor space, and any installation or anchoring instructions before placing the shelf.",
    "Cabinets": "Use the cabinet to keep items together near the place they are used, whether that is an entryway, dining room, or living area. Check the space needed to open the doors and reach the contents comfortably.",
    "Coffee Tables": "Set it within easy reach of the main seating and leave an open route around it. Compare its height with your sofa seat and allow room for everyday items such as drinks, books, and remotes.",
    "Conference Tables": "Plan for chairs to be pulled out on each side while people can still walk past. If the table will be used for presentations or shared laptops, consider the placement of power points when laying out the room.",
    "Console Tables": "In an entryway, a console can hold keys and a lamp without taking up the area needed for seating. Check the depth against the available walkway before deciding where to place it.",
    "Decorative Vases": "Display it on its own or group it with pieces at different heights to make the shape stand out. If you plan to use fresh stems, check whether the vase is specified as suitable for holding water.",
    "Dining Sets": "Measure the room with the chairs pulled out, especially if a door or main walkway is nearby. Check the listed seating and set contents before comparing it with the space and seating you need.",
    "Dining Tables": "Choose the table position with enough room for chairs to move back and for people to pass behind them. Compare the listed dimensions with your dining area, including any nearby cabinet doors.",
    "Ergonomic Chairs": "Compare the chair with the height of your desk and the space beneath it. Check the listed adjustment features for this model so you can assess how it will fit your workspace.",
    "Executive Chairs": "Allow room to move the chair away from the desk when getting up. Check the seat and arm height against your desk, particularly if you want the chair to tuck underneath.",
    "Floor Lamps": "Place it near the seat or corner you want to light, with the base clear of the main walkway. Check the bulb requirements and the position of the nearest power outlet before deciding where it will stand.",
    "Footstools": "Pair it with a chair or sofa and compare its height with the seat for a comfortable leg position. Leave room to move it aside when you need a wider path around the seating area.",
    "King Beds": "Plan for access on both sides if you are adding bedside tables. Check the bed frame dimensions and mattress compatibility, and allow clearance for nearby doors and drawers.",
    "Chaise Lounges": "Use the chaise as a reading seat or a separate place to stretch out beside the main seating. Measure its full length and leave room to approach the seat without obstructing the walkway.",
    "Mirrors": "Position the mirror to reflect a view or light source you want to bring into the room. Check its dimensions and the mounting instructions before choosing the wall and fixings.",
    "Nesting Tables": "Keep the tables together when floor space is tight and move them apart when more surfaces are needed. Consider where each table will sit when in use so it remains within reach without blocking the room.",
    "Office Desks": "Measure the space for your chair as well as the desk, including room to move back from the work surface. Plan where screens, chargers, and task lighting will sit in relation to the nearest power points.",
    "Pouffes": "Set it beside a lounge chair as a footrest or move it closer when extra informal seating is needed. Check its height next to the surrounding furniture and keep the main walkway clear.",
    "Queen Beds": "Check the full frame footprint and the mattress size specified for this model. Leave enough clearance for bedside furniture and for wardrobe doors or drawers to open.",
    "Side Tables": "Check the table height against the sofa arm or chair seat so everyday items are easy to reach. Decide what you want to set on it, such as a lamp or a drink, before choosing its position.",
    "Sideboards": "A sideboard can keep tableware close to the dining table while leaving the tabletop free. Allow clearance in front for doors or drawers and check that it will not narrow a busy route through the room.",
    "Storage Furniture": "Think about where you use the items you want to store and place the unit nearby. Compare its dimensions with the available floor area and allow for access to any compartments.",
    "Storage Ottomans": "Place it where you can reach the storage area without shifting other furniture. In a seating arrangement, compare its height with the sofa or chair and leave room to walk around it.",
    "Study Tables": "Allow enough space for a chair to pull back and check the depth you need for books, a laptop, or a desk lamp. Position the table where there is useful light and a nearby outlet if you need one.",
    "Table Lamps": "Use it to light a particular part of a room, such as a bedside table or a reading corner. Check the height relative to where you sit and the listed bulb requirements before buying.",
    "TV Units": "Compare the available surface with the footprint of your television and leave room for media equipment and cables. Plan the unit's position around your viewing distance and any nearby sockets.",
    "Wall Decor": "Try marking the item's dimensions on the wall before deciding where to hang it. Check how it relates to nearby furniture and follow the mounting instructions for your type of wall.",
}


def expand_descriptions(apps, schema_editor):
    product_model = apps.get_model("store", "Product")
    products = product_model.objects.using(schema_editor.connection.alias).select_related("category")
    updates = []
    for product in products.iterator(chunk_size=250):
        original = product.description.strip() or product.short_description.strip()
        if len(original) >= 200 or len(original.splitlines()) > 1:
            continue
        if not original:
            original = f"{product.name} is part of the EROMA {product.category.name} collection."
        elif not original.endswith((".", "!", "?")):
            original += "."
        note = ROOM_NOTES.get(product.category.name, (
            "Measure the place you have in mind and check the space available around nearby furniture. "
            "Use the published specifications to compare the details that matter for your room."
        ))
        product.description = f"{original} {note}"
        updates.append(product)
    products.bulk_update(updates, ["description"], batch_size=250)


class Migration(migrations.Migration):
    dependencies = [("store", "0030_validate_phone_and_pin")]
    operations = [migrations.RunPython(expand_descriptions, migrations.RunPython.noop)]
