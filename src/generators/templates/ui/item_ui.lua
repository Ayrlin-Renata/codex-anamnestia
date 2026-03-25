local p = {}

local function get_util() return require("Module:Data/Utils") end
local function get_item_util() return require("Module:Data/Item/Util") end

local i18n = {
    EN = {
        ['Yes'] = 'Yes',
        ['No'] = 'No',
        ['Item ID'] = 'Item ID', ['Item Name'] = 'Item Name', ['Description'] = 'Description',
        ['Category'] = 'Category', ['Sort ID'] = 'Sort ID', ['Item Rank'] = 'Item Rank',
        ['Stack Limit'] = 'Stack Limit', ['Weight'] = 'Weight', ['Durability'] = 'Durability',
        ['Freshness'] = 'Freshness', ['Changes To'] = 'Changes To', ['Attack Power'] = 'Attack Power',
        ['Defense'] = 'Defense', ['Magic Defense'] = 'Magic Defense', ['Breaking Power'] = 'Breaking Power',
        ['Food Points'] = 'Food Points', ['Water Points'] = 'Water Points', ['Cooldown'] = 'Cooldown',
        ['Weapon Type'] = 'Weapon Type', ['Armor Type'] = 'Armor Type', ['Accessory Type'] = 'Accessory Type',
        ['Tool Type'] = 'Tool Type', ['Loses When Broken'] = 'Loses When Broken', ['HP'] = 'HP',
        ['Physics Defense'] = 'Physics Defense', ['Mood Type'] = 'Mood Type', ['Mood Points'] = 'Mood Points',
        ['Vehicle ID'] = 'Vehicle ID', ['Fuel Duration'] = 'Fuel Duration', ['Casting ID'] = 'Casting ID',
        ['Guide ID'] = 'Guide ID',
    },
    JA = {
        ['Yes'] = 'はい',
        ['No'] = 'いいえ',
        ['Item ID'] = 'アイテムID', ['Item Name'] = 'アイテム名', ['Description'] = '説明',
        ['Category'] = 'カテゴリー', ['Sort ID'] = 'ソートID', ['Item Rank'] = 'アイテムランク',
        ['Stack Limit'] = 'スタック上限', ['Weight'] = '重量', ['Durability'] = '耐久値',
        ['Freshness'] = '鮮度', ['Changes To'] = '変化先', ['Attack Power'] = '攻撃力',
        ['Defense'] = '防御力', ['Magic Defense'] = '魔法防御力', ['Breaking Power'] = '破壊力',
        ['Food Points'] = '食料ポイント', ['Water Points'] = '水分ポイント', ['Cooldown'] = 'クールダウン',
        ['Weapon Type'] = '武器タイプ', ['Armor Type'] = '防具タイプ', ['Accessory Type'] = 'アクセサリータイプ',
        ['Tool Type'] = '道具タイプ', ['Loses When Broken'] = '破損時消失', ['HP'] = 'HP',
        ['Physics Defense'] = '物理防御', ['Mood Type'] = 'ムードタイプ', ['Mood Points'] = 'ムードポイント',
        ['Vehicle ID'] = '乗り物ID', ['Fuel Duration'] = '燃料期間', ['Casting ID'] = 'キャストID',
        ['Guide ID'] = 'ガイドID',
    }
}

local function getLang(frame)
    local langCode = frame.args.lang and frame.args.lang:upper()
    return i18n[langCode] and langCode or 'EN'
end

local function is_empty(t)
    if not t or type(t) ~= 'table' then return true end
    for _ in pairs(t) do return false end
    return true
end

local function get_primary_details(details)
    if not details or type(details) ~= 'table' then return {} end
    if details[1] == nil then return details end -- Not a list
    
    -- Prefer variant with empty system_type (All/Standard)
    for _, d in ipairs(details) do
        if d.system_type == '' or d.system_type == nil then
            return d
        end
    end
    -- Fallback to first
    return details[1] or {}
end

local function render_metadata_blocks(details_list, lang, metadata_kind, L)
    if not details_list or type(details_list) ~= 'table' then return nil end
    
    local list = details_list
    if is_empty(list) then return nil end
    if list[1] == nil and not is_empty(list) then
        list = {list} -- Wrap single object for consistent processing
    end

    local wikitext = {}
    for i, details in ipairs(list) do
        local system_label = details.system_type_name or details.system_type
        if system_label == "" then system_label = nil end
        
        local header_text = details.metadata_kind or metadata_kind or "Item"
        
        if system_label and system_label ~= "" and system_label ~= "Standard" then
            header_text = string.format("%s (%s)", header_text, system_label)
        end
        
        -- Header-like row for the variant using druid-section style
        table.insert(wikitext, string.format('<div class="druid-section druid-section-metadata-variant" style="text-align: center; margin-top: 5px;">%s</div>', header_text))
        
        local keys = {}
        for k, _ in pairs(details) do 
            if k ~= "system_type" and k ~= "system_type_name" and k ~= "mood_type_en" and k ~= "mood_type_ja" and k ~= "metadata_kind" then 
                table.insert(keys, k) 
            end
        end
        table.sort(keys)

        for _, k in ipairs(keys) do
            local display_key = string.gsub(k, "_", " ")
            display_key = string.gsub(display_key, "(%w)(%w*)", function(first, rest)
                return string.upper(first) .. string.lower(rest)
            end)
            
            -- Use localized label if available (check exact, then upper for stats like HP)
            local label = L[display_key] or L[string.upper(k)] or display_key
            
            local val = details[k]
            if k == 'mood_type' then
                val = details['mood_type_' .. string.lower(lang or 'en')] or val
            end
            
            if val and tostring(val) ~= "" then
                -- Match druid-infobox row structure exactly
                table.insert(wikitext, string.format('<div class="druid-row"><div class="druid-label">%s</div><div class="druid-data druid-data-nonempty">%s</div></div>', label, tostring(val)))
            end
        end
    end
    
    return table.concat(wikitext, "\n")
end

local function format_item_link(item_id, lang)
    if not item_id or item_id == '' then return '' end
    local item_util = get_item_util()
    local target_item = item_util.get_item_by_name_or_id(item_id)
    if not target_item then return tostring(item_id) end
    
    local nameEN = target_item.name_en or ''
    local nameJA = target_item.name_ja or ''
    
    if lang == 'JA' then
        if nameEN ~= '' and nameJA ~= '' then
            return '[[' .. nameEN .. '|' .. nameJA .. ']]'
        elseif nameJA ~= '' then
            return nameJA 
        elseif nameEN ~= '' then
            return '[[' .. nameEN .. ']]'
        end
    else
        if nameEN ~= '' then
            return '[[' .. nameEN .. ']]'
        end
    end
    return tostring(item_id)
end

local function getText(L, key)
    if not L then return key end
    return L[key] or key
end

function p.infobox(frame)
    local lang = getLang(frame)
    local L = i18n[lang]
    
    local identifier = frame.args[1]
    if not identifier or identifier == '' then
        return "''Error: No item name or ID provided.''"
    end

    local item_util = get_item_util()
    local item = item_util.get_item_by_name_or_id(identifier)
    
    if not item then
        return "''Error: Could not find item: " .. tostring(identifier) .. ".''<br>''Please check the name/ID.''"
    end

    local metadata_sources = {
        { key = 'housing_piece_details', kind = L['Housing Piece'] or 'Housing Piece' },
        { key = 'food_details', kind = L['Food'] or 'Food' },
        { key = 'weapon_details', kind = L['Weapon'] or 'Weapon' },
        { key = 'armor_details', kind = L['Armor'] or 'Armor' },
        { key = 'accessory_details', kind = L['Accessory'] or 'Accessory' },
        { key = 'material_details', kind = L['Material'] or 'Material' },
        { key = 'tool_details', kind = L['Tool'] or 'Tool' },
        { key = 'bullet_details', kind = L['Bullet'] or 'Bullet' },
        { key = 'element_details', kind = L['Element'] or 'Element' },
        { key = 'implement_details', kind = L['Implement'] or 'Implement' },
        { key = 'trap_details', kind = L['Trap'] or 'Trap' },
        { key = 'skill_book_details', kind = L['Skill Book'] or 'Skill Book' },
        { key = 'point_book_details', kind = L['Point Book'] or 'Point Book' },
        { key = 'vehicle_item_details', kind = L['Vehicle'] or 'Vehicle' },
        { key = 'fuel_item_details', kind = L['Fuel'] or 'Fuel' },
    }

    local details_list = {}
    local primary_details = nil
    
    for _, source in ipairs(metadata_sources) do
        local source_list = item[source.key]
        if source_list and not is_empty(source_list) then
            -- source_list is a proxy list
            for i = 1, 100 do -- Safe iteration for proxies
                local entry = source_list[i]
                if not entry then break end
                
                -- Create a shallow copy to inject metadata_kind
                local entry_with_kind = {}
                for k, v in pairs(entry) do entry_with_kind[k] = v end
                entry_with_kind.metadata_kind = source.kind
                table.insert(details_list, entry_with_kind)
                
                if not primary_details then
                    primary_details = entry_with_kind
                end
            end
        end
    end

    local details = primary_details or {}

    -- Prepare localized values
    local mood_type_val = nil
    if details.mood_type and details.mood_type ~= 0 and details.mood_type ~= '0' then
        mood_type_val = details['mood_type_' .. string.lower(lang)] or details.mood_type
    end

    local image = item.image or ''
    if image == '' then
        image = (item.icon_resource_name or '') .. '.png'
    end
    if image == '.png' then image = '' end

    local title_field = 'name_' .. string.lower(lang)
    local desc_field = 'description_' .. string.lower(lang)
    local title = item[title_field]
    if not title or title == '' then title = item.name_en end
    
    local description = item[desc_field]
    if not description or description == '' then description = item.description_en end

    local category_field = 'category_name_' .. string.lower(lang)
    local category = item[category_field]
    if not category or category == '' then category = item.category_name_en end

    local lose_broken_text = nil
    if details.lose_broken_item ~= nil then
        lose_broken_text = (details.lose_broken_item == 1 or details.lose_broken_item == '1') and L['Yes'] or L['No']
    end

    local args = {
        image = image,
        [getText(L, 'Item ID')] = item.id,
        title = title,
        [getText(L, 'Name (EN)')] = item.name_en,
        [getText(L, 'Name (JA)')] = item.name_ja,
        [getText(L, 'Description')] = description,
        [getText(L, 'Category')] = category,
        [getText(L, 'Sort ID')] = item.sort_id,
        [getText(L, 'Durability')] = details.durable_value,
        [getText(L, 'Attack Power')] = details.attack_power or details.attack,
        [getText(L, 'Defense')] = details.defense_power or details.defense,
        [getText(L, 'Magic Defense')] = details.magic_defense,
        [getText(L, 'Breaking Power')] = details.breaking,
        [getText(L, 'Food Points')] = details.food_point,
        [getText(L, 'Water Points')] = details.water_point,
        [getText(L, 'Cooldown')] = details.cool_down,
        [getText(L, 'Loses When Broken')] = lose_broken_text,
        ['Name (EN)'] = item.name_en,
        ['Name (JA)'] = item.name_ja,
        Description = description,
        Category = category,
        ['Sort ID'] = item.sort_id,
        Durability = details.durable_value,
        ['Attack Power'] = details.attack_power or details.attack,
        Defense = details.defense_power or details.defense,
        ['Magic Defense'] = details.magic_defense,
        ['Breaking Power'] = details.breaking,
        ['Food Points'] = details.food_point,
        ['Water Points'] = details.water_point,
        Cooldown = details.cool_down,
        ['Loses When Broken'] = lose_broken_text,
        HP = details.hp,
        ['Mood Type'] = mood_type_val,
        ['Mood Points'] = details.mood,
    }

    local metadata = render_metadata_blocks(details_list, lang, metadata_kind, L)
    if metadata and metadata ~= "" then
        -- Break out of the parent druid-row and druid-data divs to ensure seamless 2-column layout
        -- We add dummy opening tags at the end to satisfy the module's inevitable closing tags
        args.MetadataContent = "</div></div>" .. metadata .. "<div class=\"druid-row\" style=\"display:none;\"><div class=\"druid-data\">"
        args.MetadataContent_nolabel = "yes"
        args.MetadataContent_wide = "yes"
    end

    return frame:expandTemplate{
        title = 'Infobox/Item',
        args = args
    }
end

function p.history(frame)
    return "''History diff generation is currently disabled globally. View the page history instead.''"
end

function p.all(frame)
    local util = get_util()
    local all_items = util.get_all_entries("/Item.json")
    if not all_items then return "''Error: No items found.''" end

    local lang = getLang(frame)
    local L = i18n[lang]

    local lines = {}
    table.insert(lines, '{| class="wikitable sortable"')

    local columns = {
        'Item ID', 'Item Name', 'Description', 'Category', 'Sort ID', 'Item Rank',
        'Stack Limit', 'Weight', 'Durability', 'Freshness', 'Changes To', 'Attack Power',
        'Defense', 'Magic Defense', 'Breaking Power', 'Food Points', 'Water Points', 'Cooldown',
        'Loses When Broken', 'HP', 'Mood Type', 'Mood Points'
    }
    local header_cells = {}
    for _, colName in ipairs(columns) do
        table.insert(header_cells, '! ' .. L[colName])
    end
    table.insert(lines, '|-')
    table.insert(lines, table.concat(header_cells, '\n'))

    for _, item in ipairs(all_items) do
        local details_list = item.housing_piece_details or item.food_details or item.weapon_details or item.armor_details or item.accessory_details or item.tool_details or item.material_details or item.implement_details or item.bullet_details or item.element_details or item.point_book_details or item.skill_book_details or item.trap_details or item.vehicle_item_details or item.fuel_item_details or {}
        local details = get_primary_details(details_list)
        local nameEN = (item.name_en or ''):gsub("[\n\r]", "")
        local nameJA = (item.name_ja or ''):gsub("[\n\r]", "")
        local nameCell = '|'
        
        if lang == 'JA' then
            if nameEN ~= '' and nameJA ~= '' then
                nameCell = '| [[' .. nameEN .. '|' .. nameJA .. ']]'
            elseif nameJA ~= '' then
                nameCell = '| ' .. nameJA
            elseif nameEN ~= '' then
                nameCell = '| [[' .. nameEN .. ']]'
            end
        else
            if nameEN ~= '' then
                nameCell = '| [[' .. nameEN .. ']]'
            end
        end

        local category_field = 'category_name_' .. string.lower(lang)
        local category = item[category_field] or item.category_name_en or ''
        local description = item['description_' .. string.lower(lang)] or item.description_en or ''

        local changes_to_id = details.change_item_id or details.return_item_id or ''
        local changes_to_text = ''
        if changes_to_id ~= '' then
            changes_to_text = format_item_link(changes_to_id, lang)
        end
        local mood_type_text = ''
        if details.mood_type and details.mood_type ~= 0 and details.mood_type ~= '0' then
            mood_type_text = details['mood_type_' .. string.lower(lang)] or details.mood_type or ''
        end

        local lose_broken_text = nil
        if details.lose_broken_item ~= nil then
            lose_broken_text = (details.lose_broken_item == 1 or details.lose_broken_item == '1') and L['Yes'] or L['No']
        end

        local rowCells = {
            '| ' .. (item.id or ''),
            nameCell,
            '| ' .. description,
            '| ' .. category,
            '| ' .. (item.sort_id or ''),
            '| ' .. (details.item_rank or ''),
            '| ' .. (details.stack or ''),
            '| ' .. (details.weight or ''),
            '| ' .. (details.durable_value or ''),
            '| ' .. (details.freshness or ''),
            '| ' .. changes_to_text,
            '| ' .. (details.attack_power or details.attack or ''),
            '| ' .. (details.defense_power or details.defense or ''),
            '| ' .. (details.magic_defense or ''),
            '| ' .. (details.breaking or ''),
            '| ' .. (details.food_point or ''),
            '| ' .. (details.water_point or ''),
            '| ' .. (details.cool_down or ''),
            '| ' .. (lose_broken_text or ''),
            '| ' .. (details.hp or ''),
            '| ' .. mood_type_text,
            '| ' .. (details.mood or '')
        }
        table.insert(lines, '|-\n' .. table.concat(rowCells, '\n'))
    end

    table.insert(lines, '|}')
    return table.concat(lines, '\n')
end

function p.get(frame)
    local itemId = frame.args[1]
    local valpath = frame.args[2]

    if not itemId or itemId == '' then return "ERROR: NO ITEM ID" end
    if not valpath or valpath == '' then return "ERROR: NO DATA PATH" end

    local item_util = get_item_util()
    local item = item_util.get_item_by_name_or_id(itemId)
    if not item then
        return "ERROR: NO ITEM FOUND: " .. tostring(itemId)
    end

    local util = get_util()
    local function split(str, sep)
        local fields = {}
        local pattern = string.format("([^%s]+)", sep)
        string.gsub(str, pattern, function(c) fields[#fields + 1] = c end)
        return fields
    end

    local pathParts = split(valpath, '%.')
    local obj = item
    for _, key in ipairs(pathParts) do
        if type(obj) == 'table' and obj[key] ~= nil then
            obj = obj[key]
        else
            return nil
        end
    end

    if type(obj) == 'table' then
        return mw.dumpObject(obj)
    end
    return obj
end

return p
