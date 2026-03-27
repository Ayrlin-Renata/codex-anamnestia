--[[-
  UI module for rendering Clothing Items.
--]]

local p = {}

-- Utility imports
local function get_util()
    return require("Module:Data/ClothingItem/Util")
end

local function get_common()
    return require("Module:Data/Common/Fashion")
end

local function getText(L, key)
    return get_common().getText(L, key)
end

function p.infobox(frame)
    local args = frame.args
    local identifier = args[1] or args.id or args.name
    local lang = (args.lang or 'EN'):upper()
    
    local util = get_util()
    local common = get_common()
    local item = util.get_clothing_item_by_name_or_id(identifier)
    if not item then return "''Error: Clothing item not found: " .. tostring(identifier) .. ".''" end

    local title = common.get_display_name(item, lang)
    local description = item['description_' .. lang] or item.description_EN

    local rarity_label = common.rarity_map[item.rarity] or 'Common'
    local tribe_label = common.tribe_map[item.tribe] or 'Human'
    local gender_label = common.gender_map[item.gender] or 'Unisex'
    
    local L = common.get_i18n(lang)

    local ib_args = {
        title = title,
        ['Name (EN)'] = item.localize_EN,
        ['Name (JA)'] = item.localize_JA,
        ID = item.id,
        Rarity = string.format("%d (%s)", item.rarity or 0, getText(L, rarity_label)),
        Tribe = getText(L, tribe_label),
        Gender = getText(L, gender_label),
        Thumbnail = item.assetPath and (item.assetPath .. ".png") or "",
        Description = description
    }
    
    -- Extract clothing specific details
    if item.clothing_details then
        local details = item.clothing_details
        if details.sleeveLength then ib_args['Sleeve Length'] = details.sleeveLength end
        if details.sleeveWidth then ib_args['Sleeve Width'] = details.sleeveWidth end
        if details.isTuckedInByDefault ~= nil then ib_args['Tucked In'] = (details.isTuckedInByDefault == 1 and "Yes" or "No") end
    end

    return frame:expandTemplate{ title = 'Template:Infobox/FashionItem', args = ib_args }
end

function p.all(frame)
    local args = frame.args
    local lang = (args.lang or 'EN'):upper()
    local util = get_util()
    local common = get_common()
    local all_items = util.get_all_clothing_items()
    local L = common.get_i18n(lang)

    local lines = {}
    table.insert(lines, '{| class="wikitable sortable"')
    table.insert(lines, '|-')
    table.insert(lines, '! ID !! Name !! Rarity !! Tribe !! Gender !! Category !! Sort Key !! Detail Type !! Sleeve !! Tuck')

    for _, item in ipairs(all_items) do
        local name_cell = common.get_name_cell(item, lang, "clothing")
        
        local rarity_label = common.rarity_map[item.rarity] or 'Common'
        local rarity_str = string.format("%d (%s)", item.rarity or 0, getText(L, rarity_label))
        
        local tribe_label = common.tribe_map[item.tribe] or 'Human'
        local gender_label = common.gender_map[item.gender] or 'Unisex'
        
        local category = ""
        local sleeve = ""
        local tuck = ""
        if item.clothing_details then
            local d = item.clothing_details
            category = d.category or ""
            sleeve = d.sleeveLength or ""
            tuck = (d.isTuckedInByDefault == 1 and "Yes" or "No")
        end

        table.insert(lines, '|-')
        table.insert(lines, string.format('| %d || %s || %s || %s || %s || %s || %s || %s || %s || %s', 
            item.id, name_cell, rarity_str, getText(L, tribe_label), getText(L, gender_label),
            category, item.sortKey or "", item.detailType or "", sleeve, tuck))
    end

    table.insert(lines, '|}')
    return table.concat(lines, '\n')
end

return p
