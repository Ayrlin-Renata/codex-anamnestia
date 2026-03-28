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
        ['Result'] = 'Result', ['Materials'] = 'Materials', ['Facility'] = 'Facility',
        ['Other Requirements'] = 'Other Requirements', ['Durability'] = 'Durability',
        ['Inclusion'] = 'Inclusion', ['Observation Points'] = 'Observation Points',
    },
    JA = {
        ['Yes'] = 'はい', ['No'] = 'いいえ', ['None'] = 'なし',
        ['ID'] = 'ID', ['Name'] = '名称', ['Description'] = '説明',
        ['Category'] = 'カテゴリー', ['Sort ID'] = 'ソートID', ['Item Name'] = 'アイテム名',
        ['Level'] = 'レベル', ['Levels'] = 'レベル', ['Drops'] = 'ドロップ',
        ['Weight'] = '重量', ['Max Count'] = '最大数', ['Interval'] = '間隔',
        ['Weather Rules'] = '天候ルール', ['Static'] = '静的', ['Biome'] = 'バイオーム',
        ['Summon'] = '召喚', ['Point'] = 'ポイント', ['Species ID'] = '種族ID',
        ['Result'] = '結果', ['Materials'] = '材料', ['Facility'] = '施設',
        ['Other Requirements'] = 'その他の要件', ['Durability'] = '耐久性',
        ['Inclusion'] = '包含', ['Observation Points'] = '観察ポイント',
    }
}

--[[
    Detects the current language from frame arguments or parent frame.
    Returns uppercase 'EN', 'JA', etc.
--]]
function p.get_lang(frame)
    local args = frame.args or {}
    local p_args = (frame.getParent and frame:getParent()) and frame:getParent().args or {}

    local function pick(...)
        local n = select('#', ...)
        for i = 1, n do
            local v = select(i, ...)
            if v and v ~= "" then return v end
        end
        return nil
    end

    local lang = pick(args.lang, args[2], p_args.lang, p_args[2], 'EN')
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
    Safely resolves a nested value from a table given a dot-separated path.
    Example: "details.item_rank"
--]]
function p.get_nested_value(obj, path)
    if not obj or not path or path == "" then return nil end
    local current = obj
    for key in string.gmatch(path, "([^%.]+)") do
        if type(current) == "table" then
            current = current[key]
        else
            return nil
        end
    end
    return current
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
        if obj.species_id then
            ctx = "creature"
        elseif obj.localize_EN then
            ctx = "clothing" -- Default to clothing for fashion items
        else
            ctx = "item"
        end
    end
    
    local link_common = require("Module:Data/Common/Link")
    local rule = link_common.rules[ctx]
    
    -- Apply category-based display overrides if configured
    if rule and rule.category_field and rule.category_display_overrides then
        local cat_val = p.get_nested_value(obj, rule.category_field)
        if cat_val then
            for _, override in ipairs(rule.category_display_overrides) do
                if tostring(cat_val) == tostring(override.value) then
                    local postfix = override.display_postfix
                    if type(postfix) == "table" then
                        postfix = postfix[lang] or postfix.EN or ""
                    end
                    display_name = display_name .. (postfix or "")
                    break
                end
            end
        end
    end

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

--[[
    Centralized logic for extracting filter parameters from a frame.
--]]
function p.get_filter_params(frame)
    local args = frame.args or {}
    local p_args = (frame.getParent and frame:getParent()) and frame:getParent().args or {}
    
    local function pick(...)
        local n = select('#', ...)
        for i = 1, n do
            local v = select(i, ...)
            if v and v ~= "" then return v end
        end
        return nil
    end

    local filter = pick(args.filter, args.param, args[1], p_args.filter, p_args.param, p_args[2])
    local category_filter = pick(args.category, p_args.category)
    local regex_val = pick(args.regex, p_args.regex)
    local use_regex = (regex_val == 'true' or regex_val == 'yes')
    
    return filter, use_regex, category_filter
end

--[[
    Standard filtering logic. Supports literal or Lua pattern matching.
--]]
function p.matches_filter(text, filter, use_regex)
    if not filter or filter == "" then return true end
    if not text then return false end
    
    if use_regex then
        -- Lua standard pattern matching
        return string.find(text, filter) ~= nil
    else
        -- Literal, case-insensitive substring match
        return string.find(string.lower(text), string.lower(filter), 1, true) ~= nil
    end
end

return p
