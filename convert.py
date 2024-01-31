import sys
import io
import json
import base64

import nbt

# https://hub.spigotmc.org/stash/projects/SPIGOT/repos/bukkit/
# https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/
# https://github.com/Multiverse/Multiverse-Inventories/

BUKKIT_VERSION = 3465
GAME_MODES = ('SURVIVAL', 'CREATIVE', 'ADVENTURE', 'SPECTATOR')

# https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaItem.java#1394
HANDLED_TAGS = (
    'display', 'CustomModelData', 'BlockStateTag', 'RepairCost', 'Enchantments', 'HideFlags', 'Unbreakable', 'Damage',
    'PublicBukkitValues', 'AttributeModifiers', 'AttributeName', 'Name', 'Amount', 'UUIDMost', 'UUIDLeast', 'Slot',
    'Trim', 'material', 'pattern',  # Meta Armor
    'map_is_scaling', 'MapColor', 'map',  # Meta Map
    'custom_potion_effects', 'Potion', 'CustomPotionColor',  # Meta Potion
    'SkullOwner', 'SkullProfile',  # Meta Skull
    'EntityTag',  # Meta Spawn Egg
    'BlockEntityTag',  # Meta Block State
    'title', 'author', 'pages', 'resolved', 'generation',  # Meta Book
    'Fireworks',  # Meta Firework
    'StoredEnchantments',  # Meta Enchanted Book
    'Explosion',  # Meta Charge
    'Recipes',  # Meta Knowledge Book
    'BucketVariantTag',  # Meta Tropical Fish Bucket
    'Variant',  # Meta Axolotl Bucket
    'Charged', 'ChargedProjectiles',  # Meta Crossbow
    'effects',  # Meta Suspicious Stew
    'LodestoneDimension', 'LodestonePos', 'LodestoneTracked',  # Meta Compass
    'Items',  # Meta Bundle
    'instrument',  # Meta Music Instrument
)


def serialize_enchantments(enchantments_tag):
    id_to_enchant = {
        'protection': 'PROTECTION_ENVIRONMENTAL',
        'fire_protection': 'PROTECTION_FIRE',
        'feather_falling': 'PROTECTION_FALL',
        'blast_protection': 'PROTECTION_EXPLOSIONS',
        'projectile_protection': 'PROTECTION_PROJECTILE',
        'respiration': 'OXYGEN',
        'aqua_affinity': 'WATER_WORKER',
        'sharpness': 'DAMAGE_ALL',
        'smite': 'DAMAGE_UNDEAD',
        'bane_of_arthropods': 'DAMAGE_ARTHROPODS',
        'looting': 'LOOT_BONUS_MOBS',
        'sweeping': 'SWEEPING_EDGE',
        'efficiency': 'DIG_SPEED',
        'unbreaking': 'DURABILITY',
        'fortune': 'LOOT_BONUS_BLOCKS',
        'power': 'ARROW_DAMAGE',
        'punch': 'ARROW_KNOCKBACK',
        'flame': 'ARROW_FIRE',
        'infinity': 'ARROW_INFINITE',
        'luck_of_the_sea': 'LUCK',
    }

    result = {}
    for enchant in enchantments_tag:
        enchant_id = enchant['id'].value.split(':')[1]
        enchant_name = id_to_enchant.get(enchant_id, enchant_id.upper())
        result[enchant_name] = enchant['lvl'].value
    return result


def serialize_color(color_int, has_alpha=False):
    return {
        '==': 'Color',
        'ALPHA': color_int >> 24 & 0xff if has_alpha else 255,
        'RED': color_int >> 16 & 0xff,
        'BLUE': color_int >> 0 & 0xff,
        'GREEN': color_int >> 8 & 0xff
    }


def serialize_potion_effect(effect):
    return {
        '==': 'PotionEffect',
        'effect': effect['Id'].value,
        'duration': effect['Duration'].value,
        'amplifier': effect['Amplifier'].value,
        'ambient': bool(effect['Ambient'].value),
        'has-particles': bool(effect['ShowParticles'].value),
        'has-icon': bool(effect['ShowIcon'].value),
    }


def serialize_explosion_effect(effect):
    effect_types = ('BALL', 'BALL_LARGE', 'STAR', 'CREEPER', 'BURST')
    return {
                '==': 'Firework',
                'flicker': bool(effect.get('Flicker', False)),
                'trail': bool(effect.get('Trail', False)),
                'colors': [serialize_color(color) for color in effect['Colors']],  # always has color
                'fade-colors': [serialize_color(color) for color in effect.get('FadeColors', [])],
                'type': effect_types[effect['Type'].value]
            }


def serialize_modifiers(modifiers):
    result = {}
    # TODO: Implement attribute modifiers serialization
    # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaItem.java#413
    for mod in modifiers:
        pass
    return result


def serialize_meta_armor(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'ARMOR')
    if 'Trim' in meta_item_tag:
        trim = meta_item_tag['Trim']
        if 'material' in trim and 'pattern' in trim:
            meta['trim'] = {
                'material': trim['material'].value,
                'pattern': trim['pattern'].value
            }
    return meta


def serialize_meta_armor_stand(meta_item_tag):
    internal_tag = None
    if 'EntityTag' in meta_item_tag and len(meta_item_tag['EntityTag']) > 0:
        internal_tag = meta_item_tag['EntityTag']
    meta = serialize_meta_item(meta_item_tag, 'ARMOR_STAND', internal_tag)
    return meta


def serialize_meta_banner(meta_item_tag):
    dye_colors = ('WHITE', 'ORANGE', 'MAGENTA', 'LIGHT_BLUE', 'YELLOW', 'LIME', 'PINK', 'GRAY',
                  'LIGHT_GRAY', 'CYAN', 'PURPLE', 'BLUE', 'BROWN', 'GREEN', 'RED', 'BLACK')
    meta = serialize_meta_item(meta_item_tag, 'BANNER')
    entity_tag = meta_item_tag.get('BlockEntityTag')
    if entity_tag is None:
        return meta
    if 'Base' in entity_tag:
        meta['base-color'] = dye_colors[entity_tag['Base'].value]
    if 'Patterns' in entity_tag and len(entity_tag['Patterns']) > 0:
        meta['patterns'] = []
        for pattern in entity_tag['Patterns']:
            meta['patterns'].append(
                {
                    '==': 'Pattern',
                    'color': dye_colors[pattern['Color'].value],
                    'pattern': pattern['Pattern'].value
                }
            )
    return meta


def serialize_meta_block_state(meta_item_tag, item_type):
    internal_tag = meta_item_tag.get('BlockEntityTag')
    meta = serialize_meta_item(meta_item_tag, 'TILE_ENTITY', internal_tag)
    meta['blockMaterial'] = item_type
    return meta


def serialize_meta_book(meta_item_tag, meta_type='BOOK'):
    meta = serialize_meta_item(meta_item_tag, meta_type)
    if 'title' in meta_item_tag:
        meta['title'] = meta_item_tag['title'].value
    if 'author' in meta_item_tag:
        meta['author'] = meta_item_tag['author'].value
    if 'pages' in meta_item_tag:
        pages = meta_item_tag['pages']
        # TODO: Implement book pages normalization
        # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaBook.java#111
        # max_page_length = 320
        # if meta_type == 'BOOK_SIGNED':
        #    page = CraftChatMessage.fromJSONOrStringToJSON(page, nullable=false, keepNewlines=true, max_page_length, checkJsonContentLength=false)
        # else:
        #    pages = [page[:max_page_length] for page in pages]
        meta['pages'] = list(pages)
    if 'resolved' in meta_item_tag:
        meta['resolved'] = bool(meta_item_tag['resolved'].value)
    if 'generation' in meta_item_tag:
        meta['generation'] = meta_item_tag['generation'].value
    return meta


def serialize_meta_book_signed(meta_item_tag):
    meta = serialize_meta_book(meta_item_tag, 'BOOK_SIGNED')
    return meta


def serialize_meta_skull(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'SKULL')
    # TODO: Implement skull owner profile serialization
    # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaSkull.java
    if 'SkullOwner' in meta_item_tag:
        # meta['skull-owner'] = meta_item_tag['SkullOwner'] # TAG_String or TAG_Compound
        # GameProfileSerializer.readGameProfile(TAG_Compound)
        # GameProfile(TAG_String) # UUID ?
        # {
        #     '==': 'PlayerProfile',
        #     'uniqueId': None,
        #     'name': None,
        #     'properties': []
        # }
        pass
    if 'BlockEntityTag' in meta_item_tag and 'note_block_sound' in meta_item_tag['BlockEntityTag']:
        meta['note_block_sound'] = meta_item_tag['BlockEntityTag']['note_block_sound'].value
    return meta


def serialize_meta_leather_armor(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'LEATHER_ARMOR')
    if 'display' in meta_item_tag and 'color' in meta_item_tag['display']:
        meta['color'] = serialize_color(meta_item_tag['display']['color'].value)
    return meta


def serialize_meta_colorable_armor(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'COLORABLE_ARMOR')
    if 'display' in meta_item_tag and 'color' in meta_item_tag['display']:
        meta['color'] = serialize_color(meta_item_tag['display']['color'].value)
    return meta


def serialize_meta_map(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'MAP')
    if 'map' in meta_item_tag:
        meta['map-id'] = meta_item_tag['map'].value
    if 'map_is_scaling' in meta_item_tag:
        meta['scaling'] = bool(meta_item_tag['map_is_scaling'].value)
    if 'display' in meta_item_tag and 'MapColor' in meta_item_tag['display']:
        meta['display-map-color'] = serialize_color(meta_item_tag['display']['MapColor'].value)
    return meta


def serialize_meta_potion(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'POTION')
    if 'Potion' in meta_item_tag and meta_item_tag['Potion'].value != 'empty':
        meta['potion-type'] = meta_item_tag['Potion'].value
    if 'CustomPotionColor' in meta_item_tag:
        meta['custom-color'] = serialize_color(meta_item_tag['CustomPotionColor'].value)
    if 'custom_potion_effects' in meta_item_tag:
        meta['custom-effects'] = [serialize_potion_effect(effect) for effect in meta_item_tag['custom_potion_effects']]
    return meta


def serialize_meta_spawn_egg(meta_item_tag):
    internal_tag = None
    if 'EntityTag' in meta_item_tag and len(meta_item_tag['EntityTag']) > 0:
        internal_tag = meta_item_tag['EntityTag']
    meta = serialize_meta_item(meta_item_tag, 'SPAWN_EGG', internal_tag)
    return meta


def serialize_meta_enchanted_book(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'ENCHANTED')
    meta['stored-enchants'] = serialize_enchantments(meta_item_tag['StoredEnchantments'])
    return meta


def serialize_meta_firework(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'FIREWORK')
    if 'Fireworks' in meta_item_tag:
        fireworks = meta_item_tag['Fireworks']
        meta['power'] = fireworks['Flight'].value
        if 'Explosions' in fireworks:
            meta['firework-effects'] = [serialize_explosion_effect(effect) for effect in fireworks['Explosions']]
    return meta


def serialize_meta_charge(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'FIREWORK_EFFECT')
    if 'Explosion' in meta_item_tag:
        meta['firework-effect'] = serialize_explosion_effect(meta_item_tag['Explosion'])
    return meta


def serialize_meta_knowledge_book(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'KNOWLEDGE_BOOK')
    # TODO: Test knowledge book
    if 'Recipes' in meta_item_tag and len(meta_item_tag['Recipes']) > 0:
        meta['Recipes'] = list(meta_item_tag['Recipes'])
    return meta


def serialize_meta_tropical_fish_bucket(meta_item_tag):
    internal_tag = None
    if 'EntityTag' in meta_item_tag and len(meta_item_tag['EntityTag']) > 0:
        internal_tag = meta_item_tag['EntityTag']
    meta = serialize_meta_item(meta_item_tag, 'TROPICAL_FISH_BUCKET', internal_tag)
    if 'BucketVariantTag' in meta_item_tag:
        meta['fish-variant'] = meta_item_tag['BucketVariantTag'].value
    return meta


def serialize_meta_axolotl_bucket(meta_item_tag):
    internal_tag = None
    if 'EntityTag' in meta_item_tag and len(meta_item_tag['EntityTag']) > 0:
        internal_tag = meta_item_tag['EntityTag']
    meta = serialize_meta_item(meta_item_tag, 'AXOLOTL_BUCKET', internal_tag)
    if 'Variant' in meta_item_tag:
        meta['axolotl-variant'] = meta_item_tag['Variant'].value
    return meta


def serialize_meta_crossbow(meta_item_tag):
    # TODO: Test crossbow (charged projectiles)
    meta = serialize_meta_item(meta_item_tag, 'CROSSBOW')
    meta['charged'] = bool(meta_item_tag['Charged'].value)
    if 'ChargedProjectiles' in meta_item_tag and len(meta_item_tag['ChargedProjectiles']) > 0:
        meta['charged-projectiles'] = [serialize_item_stack(item_stack)
                                       for item_stack
                                       in meta_item_tag['ChargedProjectiles']]
    return meta


def serialize_meta_suspicious_stew(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'SUSPICIOUS_STEW')
    if 'effects' in meta_item_tag:
        meta['effects'] = [serialize_potion_effect(effect) for effect in meta_item_tag['effects']]
    return meta


def serialize_meta_entity_tag(meta_item_tag):
    internal_tag = None
    if 'EntityTag' in meta_item_tag and len(meta_item_tag['EntityTag']) > 0:
        internal_tag = meta_item_tag['EntityTag']
    meta = serialize_meta_item(meta_item_tag, 'ENTITY_TAG', internal_tag)
    return meta


def serialize_meta_compass(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'COMPASS')
    if 'LodestoneDimension' in meta_item_tag and 'LodestonePos' in meta_item_tag:
        meta['LodestonePosWorld'] = meta_item_tag['LodestoneDimension'].value
        meta['LodestonePosX'] = meta_item_tag['LodestonePos']['X'].value
        meta['LodestonePosY'] = meta_item_tag['LodestonePos']['Y'].value
        meta['LodestonePosZ'] = meta_item_tag['LodestonePos']['Z'].value
    if 'LodestoneTracked' in meta_item_tag:
        meta['LodestoneTracked'] = bool(meta_item_tag['LodestoneTracked'].value)
    return meta


def serialize_meta_bundle(meta_item_tag):
    # TODO: Test Bundle
    meta = serialize_meta_item(meta_item_tag, 'BUNDLE')
    if 'Items' in meta_item_tag and len(meta_item_tag['Items']) > 0:
        meta['items'] = [serialize_item_stack(item_stack) for item_stack in meta_item_tag['Items']]
    return meta


def serialize_meta_music_instrument(meta_item_tag):
    meta = serialize_meta_item(meta_item_tag, 'MUSIC_INSTRUMENT')
    if 'instrument' in meta_item_tag:
        meta['instrument'] = meta_item_tag['instrument'].value
    return meta


def serialize_meta_item(meta_item_tag, meta_type='UNSPECIFIC', internal_tag=None):
    # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaItem.java
    meta = {
        '==': 'ItemMeta',
        'meta-type': meta_type
    }

    if 'display' in meta_item_tag:
        display = meta_item_tag['display']
        if 'Name' in display:
            meta['display-name'] = display['Name'].value
        if 'LocName' in display:
            meta['loc-name'] = display['LocName'].value
        if 'Lore' in display and len(display['Lore']) > 0:
            # TODO: Test item lore
            meta['lore'] = list(display['Lore'])

    if 'CustomModelData' in meta_item_tag:
        meta['custom-model-data'] = meta_item_tag['CustomModelData'].value

    if 'BlockStateTag' in meta_item_tag:
        # TODO: Implement item BlockStateTag serialization
        # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaItem.java#1250
        # blockData = meta_item_tag['BlockStateTag'] # TAG_Compound
        # meta['BlockStateTag'] = CraftNBTTagConfigSerializer.serialize(blockData)
        #       -> return SnbtPrinterTagVisitor().visit(blockData) (net.minecraft.nbt.SnbtPrinterTagVisitor)
        pass

    if 'Enchantments' in meta_item_tag and len(meta_item_tag['Enchantments']) > 0:
        meta['enchants'] = serialize_enchantments(meta_item_tag['Enchantments'])

    if 'AttributeModifiers' in meta_item_tag and len(meta_item_tag['AttributeModifiers']) > 0:
        meta['attribute-modifiers'] = serialize_modifiers(meta_item_tag['AttributeModifiers'])

    if 'RepairCost' in meta_item_tag and meta_item_tag['RepairCost'].value > 0:
        meta['repair-cost'] = meta_item_tag['RepairCost'].value

    if 'HideFlags' in meta_item_tag:
        # TODO: Test item hide flags
        hide_flag = meta_item_tag['HideFlags'].value
        item_flags = zip(format(hide_flag, '08b'),
                         ('HIDE_ARMOR_TRIM', 'HIDE_DYE', 'HIDE_POTION_EFFECTS', 'HIDE_PLACED_ON',
                          'HIDE_DESTROYS', 'HIDE_UNBREAKABLE', 'HIDE_ATTRIBUTES', 'HIDE_ENCHANTS')
                         )
        meta['ItemFlags'] = [flag for bit, flag in item_flags if bit == '1']

    if 'Unbreakable' in meta_item_tag:
        meta['Unbreakable'] = bool(meta_item_tag['Unbreakable'].value)

    if 'Damage' in meta_item_tag and meta_item_tag['Damage'].value > 0:
        meta['Damage'] = meta_item_tag['Damage'].value

    internal = [meta_item_tag[tag] for tag in meta_item_tag if tag not in HANDLED_TAGS]
    if internal_tag is not None:
        internal.append(internal_tag)
    if len(internal) > 0:
        with io.BytesIO() as out:
            internal_nbt = nbt.nbt.NBTFile()
            internal_nbt.tags = internal
            internal_nbt.write_file(fileobj=out)
            meta['internal'] = base64.b64encode(out.getvalue()).decode('utf-8')

    # TODO: Implement item custom tags serialization
    # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/craftbukkit/browse/src/main/java/org/bukkit/craftbukkit/inventory/CraftMetaItem.java#1293
    # Store custom tags, wrapped in their compound
    # meta_item_tag['PublicBukkitValues']

    return meta


def serialize_meta_fn(item_type: str) -> ():
    funcs_map = {
        # ('AIR',): None,
        ('WRITTEN_BOOK',): serialize_meta_book_signed,
        ('WRITABLE_BOOK',): serialize_meta_book,
        ('CREEPER_HEAD', 'CREEPER_WALL_HEAD', 'DRAGON_HEAD', 'DRAGON_WALL_HEAD', 'PIGLIN_HEAD', 'PIGLIN_WALL_HEAD',
         'PLAYER_HEAD', 'PLAYER_WALL_HEAD', 'SKELETON_SKULL', 'SKELETON_WALL_SKULL', 'WITHER_SKELETON_SKULL',
         'WITHER_SKELETON_WALL_SKULL', 'ZOMBIE_HEAD', 'ZOMBIE_WALL_HEAD',): serialize_meta_skull,
        ('CHAINMAIL_HELMET', 'CHAINMAIL_CHESTPLATE', 'CHAINMAIL_LEGGINGS', 'CHAINMAIL_BOOTS', 'DIAMOND_HELMET',
         'DIAMOND_CHESTPLATE', 'DIAMOND_LEGGINGS', 'DIAMOND_BOOTS', 'GOLDEN_HELMET', 'GOLDEN_CHESTPLATE',
         'GOLDEN_LEGGINGS', 'GOLDEN_BOOTS', 'IRON_HELMET', 'IRON_CHESTPLATE', 'IRON_LEGGINGS', 'IRON_BOOTS',
         'NETHERITE_HELMET', 'NETHERITE_CHESTPLATE', 'NETHERITE_LEGGINGS', 'NETHERITE_BOOTS',
         'TURTLE_HELMET',): serialize_meta_armor,
        ('LEATHER_HELMET', 'LEATHER_CHESTPLATE', 'LEATHER_LEGGINGS', 'LEATHER_BOOTS',): serialize_meta_colorable_armor,
        ('LEATHER_HORSE_ARMOR',): serialize_meta_leather_armor,
        ('POTION', 'SPLASH_POTION', 'LINGERING_POTION', 'TIPPED_ARROW',): serialize_meta_potion,
        ('FILLED_MAP',): serialize_meta_map,
        ('FIREWORK_ROCKET',): serialize_meta_firework,
        ('FIREWORK_STAR',): serialize_meta_charge,
        ('ENCHANTED_BOOK',): serialize_meta_enchanted_book,
        ('BLACK_BANNER', 'BLACK_WALL_BANNER', 'BLUE_BANNER', 'BLUE_WALL_BANNER', 'BROWN_BANNER', 'BROWN_WALL_BANNER',
         'CYAN_BANNER', 'CYAN_WALL_BANNER', 'GRAY_BANNER', 'GRAY_WALL_BANNER', 'GREEN_BANNER', 'GREEN_WALL_BANNER',
         'LIGHT_BLUE_BANNER', 'LIGHT_BLUE_WALL_BANNER', 'LIGHT_GRAY_BANNER', 'LIGHT_GRAY_WALL_BANNER', 'LIME_BANNER',
         'LIME_WALL_BANNER', 'MAGENTA_BANNER', 'MAGENTA_WALL_BANNER', 'ORANGE_BANNER', 'ORANGE_WALL_BANNER',
         'PINK_BANNER', 'PINK_WALL_BANNER', 'PURPLE_BANNER', 'PURPLE_WALL_BANNER', 'RED_BANNER', 'RED_WALL_BANNER',
         'WHITE_BANNER', 'WHITE_WALL_BANNER', 'YELLOW_BANNER', 'YELLOW_WALL_BANNER',): serialize_meta_banner,
        ('ALLAY_SPAWN_EGG', 'AXOLOTL_SPAWN_EGG', 'BAT_SPAWN_EGG', 'BEE_SPAWN_EGG', 'BLAZE_SPAWN_EGG',
         'BREEZE_SPAWN_EGG', 'CAT_SPAWN_EGG', 'CAMEL_SPAWN_EGG', 'CAVE_SPIDER_SPAWN_EGG', 'CHICKEN_SPAWN_EGG',
         'COD_SPAWN_EGG', 'COW_SPAWN_EGG', 'CREEPER_SPAWN_EGG', 'DOLPHIN_SPAWN_EGG', 'DONKEY_SPAWN_EGG',
         'DROWNED_SPAWN_EGG', 'ELDER_GUARDIAN_SPAWN_EGG', 'ENDER_DRAGON_SPAWN_EGG', 'ENDERMAN_SPAWN_EGG',
         'ENDERMITE_SPAWN_EGG', 'EVOKER_SPAWN_EGG', 'FOX_SPAWN_EGG', 'FROG_SPAWN_EGG', 'GHAST_SPAWN_EGG',
         'GLOW_SQUID_SPAWN_EGG', 'GOAT_SPAWN_EGG', 'GUARDIAN_SPAWN_EGG', 'HOGLIN_SPAWN_EGG', 'HORSE_SPAWN_EGG',
         'HUSK_SPAWN_EGG', 'IRON_GOLEM_SPAWN_EGG', 'LLAMA_SPAWN_EGG', 'MAGMA_CUBE_SPAWN_EGG', 'MOOSHROOM_SPAWN_EGG',
         'MULE_SPAWN_EGG', 'OCELOT_SPAWN_EGG', 'PANDA_SPAWN_EGG', 'PARROT_SPAWN_EGG', 'PHANTOM_SPAWN_EGG',
         'PIGLIN_BRUTE_SPAWN_EGG', 'PIGLIN_SPAWN_EGG', 'PIG_SPAWN_EGG', 'PILLAGER_SPAWN_EGG', 'POLAR_BEAR_SPAWN_EGG',
         'PUFFERFISH_SPAWN_EGG', 'RABBIT_SPAWN_EGG', 'RAVAGER_SPAWN_EGG', 'SALMON_SPAWN_EGG', 'SHEEP_SPAWN_EGG',
         'SHULKER_SPAWN_EGG', 'SILVERFISH_SPAWN_EGG', 'SKELETON_HORSE_SPAWN_EGG', 'SKELETON_SPAWN_EGG',
         'SLIME_SPAWN_EGG', 'SNIFFER_SPAWN_EGG', 'SNOW_GOLEM_SPAWN_EGG', 'SPIDER_SPAWN_EGG', 'SQUID_SPAWN_EGG',
         'STRAY_SPAWN_EGG', 'STRIDER_SPAWN_EGG', 'TADPOLE_SPAWN_EGG', 'TRADER_LLAMA_SPAWN_EGG',
         'TROPICAL_FISH_SPAWN_EGG', 'TURTLE_SPAWN_EGG', 'VEX_SPAWN_EGG', 'VILLAGER_SPAWN_EGG', 'VINDICATOR_SPAWN_EGG',
         'WANDERING_TRADER_SPAWN_EGG', 'WARDEN_SPAWN_EGG', 'WITCH_SPAWN_EGG', 'WITHER_SKELETON_SPAWN_EGG',
         'WITHER_SPAWN_EGG', 'WOLF_SPAWN_EGG', 'ZOGLIN_SPAWN_EGG', 'ZOMBIE_HORSE_SPAWN_EGG', 'ZOMBIE_SPAWN_EGG',
         'ZOMBIE_VILLAGER_SPAWN_EGG', 'ZOMBIFIED_PIGLIN_SPAWN_EGG',): serialize_meta_spawn_egg,
        ('ARMOR_STAND',): serialize_meta_armor_stand,
        ('KNOWLEDGE_BOOK',): serialize_meta_knowledge_book,
        ('FURNACE', 'CHEST', 'TRAPPED_CHEST', 'JUKEBOX', 'DISPENSER', 'DROPPER', 'ACACIA_HANGING_SIGN', 'ACACIA_SIGN',
         'ACACIA_WALL_HANGING_SIGN', 'ACACIA_WALL_SIGN', 'BAMBOO_HANGING_SIGN', 'BAMBOO_SIGN',
         'BAMBOO_WALL_HANGING_SIGN', 'BAMBOO_WALL_SIGN', 'BIRCH_HANGING_SIGN', 'BIRCH_SIGN', 'BIRCH_WALL_HANGING_SIGN',
         'BIRCH_WALL_SIGN', 'CHERRY_HANGING_SIGN', 'CHERRY_SIGN', 'CHERRY_WALL_HANGING_SIGN', 'CHERRY_WALL_SIGN',
         'CRIMSON_HANGING_SIGN', 'CRIMSON_SIGN', 'CRIMSON_WALL_HANGING_SIGN', 'CRIMSON_WALL_SIGN',
         'DARK_OAK_HANGING_SIGN', 'DARK_OAK_SIGN', 'DARK_OAK_WALL_HANGING_SIGN', 'DARK_OAK_WALL_SIGN',
         'JUNGLE_HANGING_SIGN', 'JUNGLE_SIGN', 'JUNGLE_WALL_HANGING_SIGN', 'JUNGLE_WALL_SIGN', 'MANGROVE_HANGING_SIGN',
         'MANGROVE_SIGN', 'MANGROVE_WALL_HANGING_SIGN', 'MANGROVE_WALL_SIGN', 'OAK_HANGING_SIGN', 'OAK_SIGN',
         'OAK_WALL_HANGING_SIGN', 'OAK_WALL_SIGN', 'SPRUCE_HANGING_SIGN', 'SPRUCE_SIGN', 'SPRUCE_WALL_HANGING_SIGN',
         'SPRUCE_WALL_SIGN', 'WARPED_HANGING_SIGN', 'WARPED_SIGN', 'WARPED_WALL_HANGING_SIGN', 'WARPED_WALL_SIGN',
         'SPAWNER', 'BREWING_STAND', 'ENCHANTING_TABLE', 'COMMAND_BLOCK', 'REPEATING_COMMAND_BLOCK',
         'CHAIN_COMMAND_BLOCK', 'BEACON', 'DAYLIGHT_DETECTOR', 'HOPPER', 'COMPARATOR', 'SHIELD', 'STRUCTURE_BLOCK',
         'SHULKER_BOX', 'WHITE_SHULKER_BOX', 'ORANGE_SHULKER_BOX', 'MAGENTA_SHULKER_BOX', 'LIGHT_BLUE_SHULKER_BOX',
         'YELLOW_SHULKER_BOX', 'LIME_SHULKER_BOX', 'PINK_SHULKER_BOX', 'GRAY_SHULKER_BOX', 'LIGHT_GRAY_SHULKER_BOX',
         'CYAN_SHULKER_BOX', 'PURPLE_SHULKER_BOX', 'BLUE_SHULKER_BOX', 'BROWN_SHULKER_BOX', 'GREEN_SHULKER_BOX',
         'RED_SHULKER_BOX', 'BLACK_SHULKER_BOX', 'ENDER_CHEST', 'BARREL', 'BELL', 'BLAST_FURNACE', 'CAMPFIRE',
         'SOUL_CAMPFIRE', 'JIGSAW', 'LECTERN', 'SMOKER', 'BEEHIVE', 'BEE_NEST', 'SCULK_CATALYST', 'SCULK_SHRIEKER',
         'SCULK_SENSOR', 'CALIBRATED_SCULK_SENSOR', 'CHISELED_BOOKSHELF', 'DECORATED_POT', 'SUSPICIOUS_SAND',
         'SUSPICIOUS_GRAVEL', 'CRAFTER', 'TRIAL_SPAWNER',): serialize_meta_block_state,
        ('TROPICAL_FISH_BUCKET',): serialize_meta_tropical_fish_bucket,
        ('AXOLOTL_BUCKET',): serialize_meta_axolotl_bucket,
        ('CROSSBOW',): serialize_meta_crossbow,
        ('SUSPICIOUS_STEW',): serialize_meta_suspicious_stew,
        ('COD_BUCKET', 'PUFFERFISH_BUCKET', 'SALMON_BUCKET', 'ITEM_FRAME', 'GLOW_ITEM_FRAME',
         'PAINTING',): serialize_meta_entity_tag,
        ('COMPASS',): serialize_meta_compass,
        ('BUNDLE',): serialize_meta_bundle,
        ('GOAT_HORN',): serialize_meta_music_instrument,
    }

    for item_types, fn in funcs_map.items():
        if item_type in item_types:
            return fn
    return serialize_meta_item  # default serialize meta function


def get_item_meta(item_type, meta_item_tag):
    serialize_fn = serialize_meta_fn(item_type)
    if serialize_fn is serialize_meta_block_state:
        meta = serialize_fn(meta_item_tag, item_type)
    else:
        meta = serialize_fn(meta_item_tag)
    return meta


def serialize_item_stack(item_tag):
    # https://hub.spigotmc.org/stash/projects/SPIGOT/repos/bukkit/browse/src/main/java/org/bukkit/inventory/ItemStack.java#466
    item_data = {
        '==': 'org.bukkit.inventory.ItemStack',
        'v': BUKKIT_VERSION,
        'type': item_tag['id'].value.split(':')[1].upper(),
    }

    # add item amount
    if item_tag['Count'].value != 1:
        item_data['amount'] = item_tag['Count'].value

    # add item meta
    if 'tag' in item_tag:
        item_data['meta'] = get_item_meta(item_data['type'], item_tag['tag'])

    return item_data


def serialize_player_nbt(player_nbt, mv_world):
    # https://github.com/Multiverse/Multiverse-Inventories/blob/main/src/main/java/com/onarandombox/multiverseinventories/share/Sharables.java
    game_mode = GAME_MODES[player_nbt['playerGameType'].value]

    # Build default empty json structure
    json_data = {
        game_mode: {
            'inventoryContents': {},
            'offHandItem': {
                "==": "org.bukkit.inventory.ItemStack",
                "v": BUKKIT_VERSION,
                "type": "AIR",
                "amount": 0
            },
            'potions': [],
            'enderChestContents': {},
            'armorContents': {},
        }
    }

    # Parse inventory
    for tag in player_nbt['Inventory']:
        slot = tag['Slot'].value
        if slot >= 100:
            json_data[game_mode]['armorContents'][str(slot - 100)] = serialize_item_stack(tag)
        elif slot == -106:
            json_data[game_mode]['offHandItem'] = serialize_item_stack(tag)
        else:
            json_data[game_mode]['inventoryContents'][str(slot)] = serialize_item_stack(tag)

    # Parse Ender chest
    for tag in player_nbt['EnderItems']:
        json_data[game_mode]['enderChestContents'][str(tag['Slot'].value)] = serialize_item_stack(tag)

    dimensions = {
        'minecraft:overworld': '',
        'minecraft:the_nether': '_nether',
        'minecraft:the_end': '_the_end',
    }

    # Parse last location
    json_data[game_mode]['lastLocation'] = {
        '==': 'org.bukkit.Location',
        'world': mv_world + dimensions[player_nbt['Dimension'].value],
        'x': player_nbt['Pos'][0].value,
        'y': player_nbt['Pos'][1].value,
        'z': player_nbt['Pos'][2].value,
        'pitch': player_nbt['Rotation'][0].value,
        'yaw': player_nbt['Rotation'][1].value,
    }

    # Parse spawn location
    json_data[game_mode]['bedSpawnLocation'] = {
        '==': 'org.bukkit.Location',
        'world': mv_world + dimensions[player_nbt['SpawnDimension'].value],
        'x': player_nbt['SpawnX'].value,
        'y': player_nbt['SpawnY'].value,
        'z': player_nbt['SpawnZ'].value,
        'pitch': 0,
        'yaw': player_nbt['SpawnAngle'].value
    }

    # Parse potion effects
    if 'ActiveEffects' in player_nbt:
        json_data[game_mode]['potions'] = [serialize_potion_effect(effect) for effect in player_nbt['ActiveEffects']]

    # Parse stats
    json_data[game_mode]['stats'] = {
        'ex': player_nbt['foodExhaustionLevel'].valuestr(),  # Float
        'ma': '300',  # Integer (max air)
        'fl': player_nbt['foodLevel'].valuestr(),  # Integer
        'el': player_nbt['XpLevel'].valuestr(),  # Integer
        'xp': player_nbt['XpP'].valuestr(),  # Float
        'hp': player_nbt['Health'].valuestr(),  # Double
        'txp': player_nbt['XpTotal'].valuestr(),  # Integer
        'fd': player_nbt['FallDistance'].valuestr(),  # Float
        'ft': player_nbt['Fire'].valuestr(),  # Integer
        'sa': player_nbt['foodSaturationLevel'].valuestr(),  # Float
        'ra': player_nbt['Air'].valuestr(),  # Integer
    }

    return json_data


def main(player_filename, mv_world='world'):
    player = nbt.nbt.NBTFile(player_filename, 'rb')

    json_data = serialize_player_nbt(player, mv_world)

    # Get player name
    name = player['bukkit']['lastKnownName'].value

    with open(name + '.json', 'w') as out_file:
        json.dump(json_data, out_file)


def test():
    player = nbt.nbt.NBTFile('76121406-7ac6-32c8-90ee-2368a675ad02.dat', 'rb')
    result = serialize_player_nbt(player, 'world')
    print(result)


if __name__ == '__main__':
    # test()
    world = sys.argv[2] if len(sys.argv) > 2 else 'world'
    main(sys.argv[1], world)
