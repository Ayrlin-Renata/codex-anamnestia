--[[ 
  Crafting UI Module
  Provides drop-in replacement for old Crafting module.
--]]

local p = {}

local function get_util() return require("Module:Data/Utils") end
local function get_craft_util() return require("Module:Data/Crafting/Util") end
local function get_ui_common() return require("Module:Data/Common/UI") end

local function getText(L, key)
    return get_ui_common().getText(L, key)
end

local function trim(s)
    if not s then return nil end
    return s:match("^%s*(.-)%s*$")
end

local function format_materials(materials, lang)
    if not materials then return "" end
    
    local common = get_ui_common()
    local L = common.get_i18n(lang)
    local parts = {}
    
    local utils = get_util()
    
    -- Using pairs instead of ipairs and avoids # to handle proxy tables
    for _, mat in pairs(materials) do
        local name = ""
        local en_name = ""
        local item_data = nil
        
        if mat.item_id and mat.item_id ~= 0 then
            item_data = utils.get_entry_by_field("/Item.json", "id", mat.item_id, false)
        elseif mat.item_category and mat.item_category ~= 0 then
            item_data = utils.get_entry_by_field("/Item.json", "category_id", mat.item_category, false)
        end
        
        if item_data then
            name = common.get_display_name(item_data, lang)
            en_name = item_data.name_en or ""
        elseif (not mat.item_id or mat.item_id == 0) and (not mat.item_category or mat.item_category == 0) then
            -- No valid item or category — skip this material
        else
            name = (mat.item_id and mat.item_id ~= 0) and ("Item " .. mat.item_id) or ("Category " .. (mat.item_category or "?"))
            en_name = name
        end
        
        if name ~= "" then
            local part = common.get_link(item_data, lang, nil, "item")
            if part == "" then part = name end -- Fallback if link fails
            
            if mat.amount and mat.amount > 0 then
                part = part .. " ×" .. mat.amount
            end
            
            if mat.reduce_durability and mat.reduce_durability > 0 then
                part = part .. string.format(" (%d %s)", mat.reduce_durability, getText(L, 'Durability'))
            end
            if mat.reduce_inclusion and mat.reduce_inclusion > 0 then
                part = part .. string.format(" (%d %s)", mat.reduce_inclusion, getText(L, 'Inclusion'))
            end
            
            table.insert(parts, part)
        end
    end
    
    if #parts == 0 then return "" end
    return table.concat(parts, ", ")
end

local function format_requirements(recipe, L)
    local parts = {}
    if recipe.observation_point and recipe.observation_point > 0 then
        table.insert(parts, getText(L, 'Observation Points') .. ": " .. recipe.observation_point)
    end
    if recipe.required_token and recipe.required_token > 0 then
        table.insert(parts, "Required Token: " .. recipe.required_token)
    end
    
    if #parts == 0 then return "N/A" end
    return table.concat(parts, "<br />")
end

local function create_wikitext_table(recipes, lang)
    local count = 0
    if recipes then
        for _ in pairs(recipes) do count = count + 1 end
    end
    
    if count == 0 then
        return "No recipes found matching the criteria."
    end
    
    local common = get_ui_common()
    local L = common.get_i18n(lang)
    local craft_util = get_craft_util()
    local utils = get_util()
    
    local wikitext = {}
    table.insert(wikitext, '{| class="wikitable sortable"')
    table.insert(wikitext, string.format('! %s !! %s !! %s !! %s',
        getText(L, 'Result'),
        getText(L, 'Facility'),
        getText(L, 'Materials'),
        getText(L, 'Other Requirements')
    ))
    
    for _, recipe in pairs(recipes) do
        table.insert(wikitext, '|-')
        
        -- Result
        local item_data = utils.get_entry_by_field("/Item.json", "id", recipe.result_item_id, false)
        local result_name = common.get_display_name(item_data, lang)
        local result_link = common.get_link(item_data, lang, nil, "item")
        table.insert(wikitext, string.format('| data-sort-value="%s" | %s ×%d', result_name, result_link, recipe.result_amount))
        
        -- Facility
        local facility_groups = {} -- base_page -> { markers = {}, display_base = "..." }
        local group_order = {}      -- To maintain order of first appearance
        local link_common = require("Module:Data/Common/Link")
        
        if recipe.recipe_groups then
            for _, group in pairs(recipe.recipe_groups) do
                local f_data = utils.get_entry_by_field("/Facility.json", "id", group.group_id, false)
                if f_data then
                    local name_en = f_data.name_en or ""
                    local name_local = common.get_display_name(f_data, lang)
                    
                    -- base_page is for the wiki link (always EN-based)
                    local base_page = link_common.get_link_target(name_en, "facility")
                    -- display_base is for the label (localized)
                    local display_base = link_common.get_link_target(name_local, "facility")
                    
                    if not facility_groups[base_page] then
                        facility_groups[base_page] = { markers = {}, display_base = display_base }
                        table.insert(group_order, base_page)
                    end
                    
                    -- Extract qualifier and ID from the LOCALIZED name string
                    local paren_content = name_local:match("%((.-)%)")
                    local marker = ""
                    if paren_content then
                        local id_match = paren_content:match("ID (%d+)")
                        local qual = paren_content:gsub(",?%s*ID %d+", ""):gsub("^%s*,%s*", ""):gsub("%s*,%s*$", "")
                        
                        if id_match then
                            if qual ~= "" then
                                marker = id_match .. " (" .. qual .. ")"
                            else
                                marker = id_match
                            end
                        else
                            marker = qual
                        end
                    end
                    
                    if marker ~= "" then
                        -- Deduplicate markers within the same base page
                        local found = false
                        for _, existing in ipairs(facility_groups[base_page].markers) do
                            if existing == marker then found = true break end
                        end
                        if not found then
                            table.insert(facility_groups[base_page].markers, marker)
                        end
                    end
                end
            end
        end
        
        local facility_parts = {}
        for _, base_page in ipairs(group_order) do
            local g = facility_groups[base_page]
            local label = g.display_base
            
            local display = ""
            if #g.markers > 0 then
                -- Try to keep numerical order for ID-based markers if possible
                table.sort(g.markers, function(a, b)
                    local an = tonumber(a:match("^(%d+)"))
                    local bn = tonumber(b:match("^(%d+)"))
                    if an and bn then return an < bn end
                    return a < b
                end)
                display = string.format("%s (ID %s)", label, table.concat(g.markers, ", "))
            else
                display = label
            end
            
            if base_page == display then
                table.insert(facility_parts, "[[" .. base_page .. "]]")
            else
                table.insert(facility_parts, "[[" .. base_page .. "|" .. display .. "]]")
            end
        end
        
        local facility_text = #facility_parts > 0 and table.concat(facility_parts, ", ") or "N/A"
        table.insert(wikitext, '| ' .. facility_text)
        
        -- Materials
        table.insert(wikitext, '| ' .. format_materials(recipe.materials, lang))
        
        -- Requirements
        table.insert(wikitext, '| ' .. format_requirements(recipe, L))
    end
    
    table.insert(wikitext, '|}')
    return table.concat(wikitext, '\n')
end

-- =[[ EXPORTED FUNCTIONS ]]= --

function p.get(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    local L = common.get_i18n(lang)
    
    local target = trim(frame.args[1] or frame:getParent().args[1])
    if not target or target == "" then
        return "<strong class=\"error\">Error: Please provide a recipe name.</strong>"
    end
    
    local recipes = get_craft_util().get_recipes_by_result(target, lang)
    if #recipes == 0 then
        return string.format("Crafting recipe for '%s' not found.", target)
    end
    
    return create_wikitext_table(recipes, lang)
end

function p.isin(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    local L = common.get_i18n(lang)
    
    local target = trim(frame.args[1] or frame:getParent().args[1])
    if not target or target == "" then
        return "<strong class=\"error\">Error: Please provide a material name.</strong>"
    end
    
    local recipes = get_craft_util().get_recipes_by_material(target, lang)
    if #recipes == 0 then
        return "No recipes found using this material."
    end
    
    return create_wikitext_table(recipes, lang)
end

function p.facility(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    local L = common.get_i18n(lang)
    
    local target = trim(frame.args[1] or frame:getParent().args[1])
    if not target or target == "" then
        return "<strong class=\"error\">Error: Please provide a facility name.</strong>"
    end
    
    local recipes = get_craft_util().get_recipes_by_facility(target, lang)
    if #recipes == 0 then
        return "No recipes found for this facility."
    end
    
    return create_wikitext_table(recipes, lang)
end

function p.all(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    
    local raw_recipes = get_craft_util().get_all_recipes()
    if not raw_recipes then
        return "No recipes found in the data module (Module:Data/Recipe_Craft.json)."
    end

    -- Copy to a regular table to allow sorting and ensure # operator works (proxies can be tricky)
    local all_recipes = {}
    for _, r in pairs(raw_recipes) do
        table.insert(all_recipes, r)
    end
    
    local count = #all_recipes
    if count == 0 then
        return "No recipes found. DEBUG: count=0, length=0, module=Module:Data/Recipe_Craft.json"
    end
    
    -- Sorting (optimized by pre-calculating names)
    local utils = get_util()
    local item_names = {}
    local function get_name(recipe)
        local id = recipe.result_item_id
        if not item_names[id] then
            local item = utils.get_entry_by_field("/Item.json", "id", id, false)
            item_names[id] = common.get_display_name(item, lang) or tostring(id)
        end
        return item_names[id]
    end
    
    table.sort(all_recipes, function(a, b)
        return get_name(a) < get_name(b)
    end)
    
    return '<div class="he-widepage">\n' .. create_wikitext_table(all_recipes, lang) .. '\n</div>'
end

return p
