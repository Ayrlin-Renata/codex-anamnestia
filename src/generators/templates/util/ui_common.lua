--[[-
  Common utility functions for all UI modules.
  Handles language detection, localization helpers, and shared UI patterns.
--]]

local p = {}

-- Global UI translations
p.i18n = {
    EN = {
        ['Yes'] = 'Yes', ['No'] = 'No', ['None'] = 'None',
        ['ID'] = 'ID', ['Name'] = 'Name', ['Description'] = 'Description',
        ['Category'] = 'Category', ['Sort ID'] = 'Sort ID', ['Item Name'] = 'Item Name',
        ['Level'] = 'Level', ['Levels'] = 'Levels', ['Drops'] = 'Drops',
        ['Weight'] = 'Weight', ['Max Count'] = 'Max Count', ['Interval'] = 'Interval',
        ['Weather Rules'] = 'Weather Rules', ['Static'] = 'Static', ['Biome'] = 'Biome',
        ['Summon'] = 'Summon', ['Point'] = 'Point', ['Species ID'] = 'Species ID',
    },
    JA = {
        ['Yes'] = 'はい', ['No'] = 'いいえ', ['None'] = 'なし',
        ['ID'] = 'ID', ['Name'] = '名称', ['Description'] = '説明',
        ['Category'] = 'カテゴリー', ['Sort ID'] = 'ソートID', ['Item Name'] = 'アイテム名',
        ['Level'] = 'レベル', ['Levels'] = 'レベル', ['Drops'] = 'ドロップ',
        ['Weight'] = '重量', ['Max Count'] = '最大数', ['Interval'] = '間隔',
        ['Weather Rules'] = '天候ルール', ['Static'] = '静的', ['Biome'] = 'バイオーム',
        ['Summon'] = '召喚', ['Point'] = 'ポイント', ['Species ID'] = '種族ID',
    }
}

--[[
    Detects the current language from frame arguments or parent frame.
    Returns uppercase 'EN', 'JA', etc.
--]]
function p.get_lang(frame)
    local args = frame.args or {}
    local p_args = (frame.getParent and frame:getParent()) and frame:getParent().args or {}
    local lang = args.lang or args[2] or p_args.lang or p_args[2] or 'EN'
    return string.upper(lang)
end

function p.get_i18n(lang)
    local l = (lang or 'EN'):upper()
    return p.i18n[l] or p.i18n.EN
end

function p.getText(L, key)
    if not L or not key or key == "" then return key or "" end
    return L[key] or key
end

--[[
    Generic name resolution with fallback strategy.
    Tries current lang, then EN, then JA, then ID.
--]]
function p.get_display_name(obj, lang, fields)
    if not obj then return "" end
    local l = (lang or 'EN'):upper()
    
    local f = fields or {}
    local current_field = f.current or ('name_' .. string.lower(l))
    local en_field = f.en or 'name_en'
    local ja_field = f.ja or 'name_ja'
    
    -- Special case for fashion items which use localize_X
    if obj.id and tostring(obj.id):match("^%d+$") and obj.localize_EN then
        current_field = 'localize_' .. l
        en_field = 'localize_EN'
        ja_field = 'localize_JA'
    end

    local name = obj[current_field]
    if not name or name == "" or name == "-" then
        name = obj[en_field]
    end
    if not name or name == "" or name == "-" then
        name = obj[ja_field]
    end
    if not name or name == "" or name == "-" then
        name = obj.id and ("Item " .. tostring(obj.id)) or ""
    end
    return tostring(name)
end

--[[
    Generic link generator.
--]]
function p.get_link(obj, lang, fields, context)
    if not obj then return "" end
    
    local display_name = p.get_display_name(obj, lang, fields)
    
    -- Always resolve link target using English name (per user request)
    -- This ensures JA display points to EN base page
    local f = fields or {}
    local en_field = f.en or 'name_en'
    if obj.localize_EN then en_field = 'localize_EN' end
    local en_name = obj[en_field] or ""
    
    -- Infer context if not provided
    local ctx = context
    if not ctx then
        if obj.localize_EN then
            ctx = "clothing" -- Default to clothing for fashion items
        elseif obj.species_id then
            ctx = "creature"
        else
            ctx = "item"
        end
    end
    
    local link_common = require("Module:Data/Common/Link")
    return link_common.get_link_markup(display_name, en_name, ctx)
end

--[[
    Renders a standard Drupal-style infobox row.
--]]
function p.render_row(label, value, is_empty_ok)
    if not is_empty_ok and (not value or tostring(value) == "" or tostring(value) == "0") then
        return ""
    end
    return string.format('<div class="druid-row"><div class="druid-label">%s</div><div class="druid-data druid-data-nonempty">%s</div></div>', label, tostring(value))
end

return p
