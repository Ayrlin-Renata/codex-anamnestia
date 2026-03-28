--[[ 
  Processing UI Module
  Provides drop-in replacement for legacy Processing module.
--]]

local p = {}

local function get_util() return require("Module:Data/Utils") end
local function get_process_util() return require("Module:Data/Processing/Util") end
local function get_ui_common() return require("Module:Data/Common/UI") end
local function get_recipe_common() return require("Module:Data/Common/Recipe") end

local function getText(L, key)
    return get_ui_common().getText(L, key)
end

local function trim(s)
    if not s then return nil end
    return s:match("^%s*(.-)%s*$")
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
    local recipe_common = get_recipe_common()
    local L = common.get_i18n(lang)
    local utils = get_util()
    
    local wikitext = {}
    table.insert(wikitext, '{| class="wikitable sortable"')
    table.insert(wikitext, string.format('! %s !! %s !! %s !! %s',
        getText(L, 'Result'),
        getText(L, 'Byproduct'),
        getText(L, 'Facility'),
        getText(L, 'Material')
    ))
    
    for _, recipe in pairs(recipes) do
        table.insert(wikitext, '|-')
        
        -- Result
        local item_data = utils.get_entry_by_field("/Item.json", "id", recipe.result_item_id, false)
        local result_name = common.get_display_name(item_data, lang)
        local result_link = common.get_link(item_data, lang, nil, "item")
        table.insert(wikitext, string.format('| data-sort-value="%s" | %s ×%d', result_name, result_link, recipe.result_amount))
        
        -- Byproduct
        table.insert(wikitext, '| ' .. recipe_common.format_byproducts(recipe.byproducts, lang))

        -- Facility
        table.insert(wikitext, '| ' .. recipe_common.format_facilities(recipe.recipe_groups, lang))
        
        -- Material
        local mat = { item_id = recipe.material_item_id, amount = recipe.material_amount }
        table.insert(wikitext, '| ' .. recipe_common.format_materials(mat, lang))
    end
    
    table.insert(wikitext, '|}')
    return table.concat(wikitext, '\n')
end

-- =[[ EXPORTED FUNCTIONS ]]= --

function p.get(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    
    local args = frame.args
    local target = trim(args[1] or args.param or frame:getParent().args[1])
    if not target or target == "" then
        local L = common.get_i18n(lang)
        return "<strong class=\"error\">" .. (getText(L, 'Error: Please provide an item name.') or "Error: Please provide an item name.") .. "</strong>"
    end
    
    local recipes = get_process_util().get_recipes_by_result(target, lang)
    if #recipes == 0 then
        return string.format("Processing recipe for '%s' not found.", target)
        -- Note: The old module had a slightly different error message, but this is consistent with our new Crafting UI.
    end
    
    return create_wikitext_table(recipes, lang)
end

function p.isin(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    
    local args = frame.args
    local target = trim(args[1] or args.param or frame:getParent().args[1])
    if not target or target == "" then
        local L = common.get_i18n(lang)
        return "<strong class=\"error\">" .. (getText(L, 'Error: Please provide a material name.') or "Error: Please provide a material name.") .. "</strong>"
    end
    
    local recipes = get_process_util().get_recipes_by_material(target, lang)
    if #recipes == 0 then
        return string.format("No processing recipes found using this material: '%s'.", target)
    end
    
    return create_wikitext_table(recipes, lang)
end

function p.facility(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    
    local args = frame.args
    local target = trim(args[1] or args.param or frame:getParent().args[1])
    if not target or target == "" then
        local L = common.get_i18n(lang)
        return "<strong class=\"error\">" .. (getText(L, 'Error: Please provide a facility name.') or "Error: Please provide a facility name.") .. "</strong>"
    end
    
    local recipes = get_process_util().get_recipes_by_facility(target, lang)
    if #recipes == 0 then
        return string.format("No processing recipes found for this facility: '%s'.", target)
    end
    
    return create_wikitext_table(recipes, lang)
end

function p.all(frame)
    local common = get_ui_common()
    local lang = common.get_lang(frame)
    local filter, use_regex = common.get_filter_params(frame)
    
    local raw_recipes = get_process_util().get_all_recipes()
    if not raw_recipes then
        return "No processing recipes found in the data module."
    end

    local utils = get_util()
    local item_names = {}
    local all_recipes = {}

    for _, r in pairs(raw_recipes) do
        local id = r.result_item_id
        if not item_names[id] then
            local item = utils.get_entry_by_field("/Item.json", "id", id, false)
            item_names[id] = common.get_display_name(item, lang) or tostring(id)
        end
        
        if common.matches_filter(item_names[id], filter, use_regex) then
            table.insert(all_recipes, r)
        end
    end
    
    if #all_recipes == 0 then
        if filter and filter ~= "" then
            return "No processing recipes found matching filter: " .. tostring(filter)
        end
        return "No processing recipes found."
    end
    
    -- Sorting
    table.sort(all_recipes, function(a, b)
        return item_names[a.result_item_id] < item_names[b.result_item_id]
    end)
    
    return '<div>\n' .. create_wikitext_table(all_recipes, lang) .. '\n</div>'
end

return p
