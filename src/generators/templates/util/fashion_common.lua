local function get_ui_common()
    return require("Module:Data/Common/UI")
end

local p = {}

p.rarity_map = { [1] = 'Common', [2] = 'Uncommon', [3] = 'Rare', [4] = 'Epic', [5] = 'Legendary' }
p.tribe_map = { [1] = 'Human', [2] = 'Beastman' }
p.gender_map = { ['f'] = 'Feminine', ['m'] = 'Masculine', ['u'] = 'Unisex' }

p.i18n = {
    EN = {
        ['Common'] = 'Common', ['Uncommon'] = 'Uncommon', ['Rare'] = 'Rare', ['Epic'] = 'Epic', ['Legendary'] = 'Legendary',
        ['Human'] = 'Human', ['Beastman'] = 'Beastman',
        ['Feminine'] = 'Feminine', ['Masculine'] = 'Masculine', ['Unisex'] = 'Unisex'
    },
    JA = {
        ['Common'] = 'コモン', ['Uncommon'] = 'アンコモン', ['Rare'] = 'レア', ['Epic'] = 'エピック', ['Legendary'] = 'レジェンダリー',
        ['Human'] = 'ヒューマン', ['Beastman'] = '亜人',
        ['Feminine'] = '女性用', ['Masculine'] = '男性用', ['Unisex'] = '男女共用'
    }
}

function p.get_i18n(lang)
    local l = (lang or 'EN'):upper()
    local L = p.i18n[l] or p.i18n.EN
    -- Merge with UI common terms
    local ui_L = get_ui_common().get_i18n(l)
    for k, v in pairs(ui_L) do
        if not L[k] then L[k] = v end
    end
    return L
end

function p.getText(L, key)
    return get_ui_common().getText(L, key)
end

function p.get_display_name(item, lang)
    return get_ui_common().get_display_name(item, lang)
end

function p.get_name_cell(item, lang, context)
    return get_ui_common().get_link(item, lang, nil, context)
end

function p.get_item_by_name_or_id(relative_path, identifier)
    if not identifier or identifier == "" then return nil end
    local id_str = mw.text.trim(tostring(identifier))
    if id_str:sub(1, 3):upper() == "ID_" then
        id_str = id_str:sub(4)
    end
    
    local util = require("Module:Data/Utils")
    local all_items = util.get_all_entries(relative_path)
    if not all_items then return nil end
    
    local numeric_id = tonumber(id_str)
    if numeric_id then
        for _, v in ipairs(all_items) do
            if v.id == numeric_id then return v end
        end
    end
    
    local lower_id = string.lower(id_str)
    for _, v in ipairs(all_items) do
        if v.localize_EN and string.lower(v.localize_EN) == lower_id then return v end
        if v.localize_JA and string.lower(v.localize_JA) == lower_id then return v end
    end
    return nil
end

return p
