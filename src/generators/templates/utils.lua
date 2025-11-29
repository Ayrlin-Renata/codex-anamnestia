--[[-
  Advanced utility functions for accessing current and historical data.
--]]

local p = {}

-- A memoization table to cache loaded data modules within a single page request.
local data_cache = {}
local codex_meta_cache = nil

--[[
  Loads a data module from the Module:Data/ namespace using the efficient mw.loadData.
  Takes a relative path, e.g., "/Creature.json" or "/History/2025-10-08/Creature.json".
  Returns the content of the data page, or nil if it doesn't exist.
--]]
local function load_data(relative_path)
    if data_cache[relative_path] then
        return data_cache[relative_path]
    end

    local clean_path = relative_path:gsub("^/+", "")
    local module_name = "Module:Data/" .. clean_path

    local success, result = pcall(mw.loadJsonData, module_name)

    if success and result then
        -- The result from loadJsonData is the data table itself.
        data_cache[relative_path] = result
        return result
    end
    return nil
end

--[[
  Safely traverses a table using a dot-separated path string.
  Example: get_value_by_path(entry, "data.stats.health")
--]]
function p.get_value_by_path(data, path)
    if type(path) ~= 'string' then return nil end
    local current = data
    for key in string.gmatch(path, "[^.]+") do
        if type(current) ~= 'table' then return nil end
        current = current[key]
    end
    return current
end

--[[
  Loads and caches the codex metadata from meta.json.
--]]
local function get_codex_meta()
    if codex_meta_cache then
        return codex_meta_cache
    end
    codex_meta_cache = load_data("/meta.json")
    return codex_meta_cache
end

--[[
  Gets a single entry from a Lua data module specified by its relative path and ID.
  Note: This is for key-value Lua tables, not lists from JSON.
--]]
function p.get_entry_by_id(relative_path, id)
    local data = load_data(relative_path)
    if not data or id == nil then
        return nil
    end
    return data[tostring(id)]
end

--[[
  Gets all entries from a data module as a list.
  Handles both wrapped JSON lists and flat Lua tables.
--]]
function p.get_all_entries(relative_path)
    local data = load_data(relative_path)
    if not data or type(data) ~= 'table' then
        return {}
    end

    -- If it has a "data" wrapper, use that.
    if data.data and type(data.data) == 'table' then
        return data.data
    end

    -- Check if the table is already an array (sequence).
    if data[1] ~= nil then
        return data
    end

    -- Otherwise, assume it's a map and extract the values into a list.
    local entries = {}
    for _, entry in pairs(data) do
        table.insert(entries, entry)
    end
    return entries
end

--[[
  Gets a list of all available historical version IDs.
--]]
function p.get_versions()
    local meta = get_codex_meta()
    return meta and meta.versions or {}
end

--[[
  Gets a specific historical version of an entry.
--]]
function p.get_historical_entry(relative_path, version, id)
    local historical_path = "/History/" .. version .. relative_path
    -- This might need adjustment if historical data is also a list
    return p.get_entry_by_id(historical_path, id)
end

--[[
  Gets the complete history of a single field for a single entry.
--]]
function p.get_field_history(relative_path, id, field_path)
    local history = {}
    local versions = p.get_versions()
    local meta = get_codex_meta()
    local codex_fields = meta and meta.codex_added_fields or {}

    for _, version in ipairs(versions) do
        local entry = p.get_historical_entry(relative_path, version, id)
        if entry then
            local value = p.get_value_by_path(entry, field_path)
            local is_codex_added = false
            for _, codex_field in ipairs(codex_fields) do
                if codex_field.version == version then
                    if codex_field.file == relative_path or codex_field.file == "*" then
                        if codex_field.field == field_path or codex_field.field == "*" then
                            is_codex_added = true
                            break
                        end
                    end
                end
            end
            history[version] = { value = value, codex_added = is_codex_added }
        end
    end
    return history
end

--[[
  Gets the complete history of an entire object, noting which fields are codex-added.
--]]
function p.get_object_history(relative_path, id)
    local history = {}
    local versions = p.get_versions()
    local meta = get_codex_meta()
    local codex_fields = meta and meta.codex_added_fields or {}

    for _, version in ipairs(versions) do
        local entry = p.get_historical_entry(relative_path, version, id)
        if entry then
            local added_fields = {}
            
            local has_wildcard = false
            for _, codex_field in ipairs(codex_fields) do
                if codex_field.version == version and (codex_field.file == relative_path or codex_field.file == "*") and codex_field.field == "*" then
                    has_wildcard = true
                    break
                end
            end

            if has_wildcard then
                for field_key, _ in pairs(entry) do
                    table.insert(added_fields, field_key)
                end
            else
                for field_key, _ in pairs(entry) do
                    for _, codex_field in ipairs(codex_fields) do
                        if codex_field.version == version then
                            if codex_field.file == relative_path or codex_field.file == "*" then
                                if codex_field.field == field_key then
                                    table.insert(added_fields, field_key)
                                end
                            end
                        end
                    end
                end
            end
            entry._codex_fields = added_fields
            history[version] = entry
        end
    end
    return history
end

--[[
  Finds the first entry in a data module that matches a specific field value.
--]]
function p.get_entry_by_field(relative_path, field, value, ignore_case)
    local all_entries = p.get_all_entries(relative_path)
    if not all_entries then
        return nil
    end

    for _, entry in ipairs(all_entries) do
        local entry_value = entry[field]
        local match_value = value

        if entry_value then
            if ignore_case then
                if type(entry_value) == 'string' and type(match_value) == 'string' then
                    if entry_value:lower() == match_value:lower() then
                        return entry
                    end
                end
            else
                if tostring(entry_value) == tostring(match_value) then
                    return entry
                end
            end
        end
    end

    return nil
end

--[[
  Finds all entries in a data module that match a specific field value.
--]]
function p.get_entries_by_field(relative_path, field, value, ignore_case)
    local all_entries = p.get_all_entries(relative_path)
    if not all_entries then
        return {}
    end

    local found_entries = {}
    for _, entry in ipairs(all_entries) do
        local entry_value = entry[field]
        local match_value = value

        if entry_value then
            if ignore_case then
                if type(entry_value) == 'string' and type(match_value) == 'string' then
                    if entry_value:lower() == match_value:lower() then
                        table.insert(found_entries, entry)
                    end
                end
            else
                if tostring(entry_value) == tostring(match_value) then
                    table.insert(found_entries, entry)
                end
            end
        end
    end

    return found_entries
end

--[[
  Finds the first entry in a data module by trying a list of fields in priority order.
--]]
function p.get_entry_by_fields(relative_path, fields, value, ignore_case)
    local fields_to_search = fields
    if type(fields) == 'string' then
        fields_to_search = { fields }
    end

    for _, field in ipairs(fields_to_search) do
        local entry = p.get_entry_by_field(relative_path, field, value, ignore_case)
        if entry then
            return entry
        end
    end
    return nil
end

return p