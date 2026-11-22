from django.db import migrations


COVER_REPLACEMENTS = {
    "categories/2026/11/2-seater-sofas_aZV9gXJ.jpg": "categories/gallery/2026/11/2_Seater.jpeg",
    "categories/2026/11/3-seater-sofas_4a1StOE.jpg": "categories/gallery/2026/11/3_Seater.jpeg",
    "categories/2026/11/accent-chairs_YVa2out.jpg": "categories/gallery/2026/11/Accent.jpeg",
    "categories/2026/11/bar-stools_rPXR9pk.jpg": "categories/gallery/2026/11/bar_stool.jpeg",
    "categories/2026/11/bedroom-benches_5LFQldT.jpg": "categories/gallery/2026/11/bedroom_bench.jpeg",
    "categories/2026/11/bedside-tables_liXRxwV.jpg": "categories/gallery/2026/11/Bedside.jpeg",
    "categories/2026/11/bookshelves_BckrwNR.jpg": "categories/gallery/2026/11/bookshelf.jpeg",
    "categories/2026/11/cabinets_Uys5dCe.jpg": "categories/gallery/2026/11/cabinets.jpeg",
    "categories/2026/11/chaise-lounges_I2t9PR7.jpg": "categories/gallery/2026/11/lounges.jpeg",
    "categories/2026/11/coffee-tables_mlS9FZT.jpg": "categories/gallery/2026/11/Coffee_table.jpeg",
    "categories/2026/11/conference-tables_IoRdIsY.jpg": "categories/gallery/2026/11/conference_table.jpeg",
    "categories/2026/11/console-tables_UCNuwYT.jpg": "categories/gallery/2026/11/console.jpeg",
    "categories/2026/11/decorative-vases_xWSlIh3.jpg": "categories/gallery/2026/11/decorative_vase.jpeg",
    "categories/2026/11/dining-chairs_TTxVSma.jpg": "categories/gallery/2026/11/dinning.jpeg",
    "categories/2026/11/dining-sets_dp4xhmx.jpg": "categories/gallery/2026/11/dinning_set.jpeg",
    "categories/2026/11/dining-tables_9oS5JWH.jpg": "categories/gallery/2026/11/dinning_table.jpeg",
    "categories/2026/11/ergonomic-chairs_xlMXp21.jpg": "categories/gallery/2026/11/Ergonomic.jpeg",
    "categories/2026/11/executive-chairs_nqH49As.jpg": "categories/gallery/2026/11/executive_chair.jpeg",
    "categories/2026/11/floor-lamps_VWBiOsl.jpg": "categories/gallery/2026/11/floor_lamp.jpeg",
    "categories/2026/11/footstools_3PAEIa0.jpg": "categories/gallery/2026/11/footstool.jpeg",
    "categories/2026/11/king-beds_zwbXWAm.jpg": "categories/gallery/2026/11/king_size.jpeg",
    "categories/2026/11/l-shaped-sofas_PqpWrS1.jpg": "categories/gallery/2026/11/L_shape.jpeg",
    "categories/2026/11/lounge-chairs_jGsKj6D.jpg": "categories/gallery/2026/11/Lounge.jpeg",
    "categories/2026/11/mirrors_CXh00Us.jpg": "categories/gallery/2026/11/mirror.jpeg",
    "categories/2026/11/modular-sofas_XVMuB2H.jpg": "categories/gallery/2026/11/modular.jpeg",
    "categories/2026/11/nesting-tables_9GldUoP.jpg": "categories/gallery/2026/11/Nesting_table.jpeg",
    "categories/2026/11/office-desks_cQBIcRZ.jpg": "categories/gallery/2026/11/office_desk.jpeg",
    "categories/2026/11/pouffes_sJew47i.jpg": "categories/gallery/2026/11/Pouffe.jpeg",
    "categories/2026/11/queen-beds_xtnNilj.jpg": "categories/gallery/2026/11/Queen_size.jpeg",
    "categories/2026/11/recliner-chairs_uKiWQ5H.jpg": "categories/gallery/2026/11/recliner.jpeg",
    "categories/2026/11/rocking-chairs_CoHu2cR.jpg": "categories/gallery/2026/11/rocking.jpeg",
    "categories/2026/11/side-tables_rmUUBAO.jpg": "categories/gallery/2026/11/side_table.jpeg",
    "categories/2026/11/sideboards_Qph47NI.jpg": "categories/sideboards.jpg",
    "categories/2026/11/sofa-beds_ESatAxJ.jpg": "categories/gallery/2026/11/sofabed.jpeg",
    "categories/2026/11/storage-ottomans_slYBirD.jpg": "categories/gallery/2026/11/Ottomans.jpeg",
    "categories/2026/11/study-tables_2b2MHNa.jpg": "categories/gallery/2026/11/Study_table.jpeg",
    "categories/2026/11/table-lamps_8sQACBw.jpg": "categories/gallery/2026/11/Table_Lamp.jpeg",
    "categories/2026/11/tv-units_ljcb9zH.jpg": "categories/gallery/2026/11/tv_unit.jpeg",
    "categories/2026/11/wall-decor_h2hta84.jpg": "categories/gallery/2026/11/wall_decor.jpeg",
}


def repair_covers(apps, schema_editor):
    categories = apps.get_model("store", "Category").objects.using(schema_editor.connection.alias)
    for previous, replacement in COVER_REPLACEMENTS.items():
        categories.filter(image=previous).update(image=replacement)


class Migration(migrations.Migration):
    dependencies = [("store", "0032_add_catalog_styling_paragraph")]
    operations = [migrations.RunPython(repair_covers, migrations.RunPython.noop)]
