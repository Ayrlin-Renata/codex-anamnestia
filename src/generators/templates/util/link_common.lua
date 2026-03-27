--[[-
  Common utility for handling wiki links and context-aware resolution.
  Handles variants (grouping to base pages) and disambiguation postfixes.
--]]

local p = {}

-- Generated rules table
p.rules = {
-- [[RULES_PLACEHOLDER]]
}

-- Resolves the actual wiki page title for a given item name and context.
function p.get_link_target(name, context)
    if not name or name == "" or name == "-" then return "" end
    local rule = p.rules[context]
    local target = name
    
    if rule then
        -- Handle variants (strip suffixes for base page grouping)
        if rule.variant_regexes then
            for _, regex in ipairs(rule.variant_regexes) do
                -- Use a function to check for exclusions before stripping
                target = mw.ustring.gsub(target, regex, function(match, inner)
                    local content = inner or match
                    if rule.variant_exclude then
                        for _, ex in ipairs(rule.variant_exclude) do
                            if content == ex then return match end -- Keep full match if excluded
                        end
                    end
                    return "" -- Strip it
                end)
            end
            -- Trim any trailing whitespace after stripping (using mw.ustring)
            target = mw.ustring.match(target, "^%s*(.-)%s*$")
        end
        
        -- Handle postfix (disambiguation)
        if rule.postfix then
            target = target .. rule.postfix
        end
    end
    
    return target
end

-- Returns full wiki link markup [[Target|Display]].
-- If target_name is provided, it is used for link resolution instead of name.
function p.get_link_markup(name, target_name, context)
    if not name or name == "" or name == "-" then return "" end
    
    -- If target_name is explicitly an empty string or "-", we don't want a link.
    -- This handles cases where a localized item has no English base page.
    if target_name == "" or target_name == "-" then
        return name
    end
    
    local link_target = target_name or name
    local resolved_target = p.get_link_target(link_target, context)
    
    if resolved_target == name then
        return "[[" .. name .. "]]"
    else
        return "[[" .. resolved_target .. "|" .. name .. "]]"
    end
end

return p
