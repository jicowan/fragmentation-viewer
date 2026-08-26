import React from 'react';
import './TagGroupSelector.css';

function TagGroupSelector({ tagKeys, selectedTagKey, onSelect, loading }) {
  return (
    <div className="tag-group-selector">
      <label htmlFor="tag-key-select">Group by Tag:</label>
      <select
        id="tag-key-select"
        value={selectedTagKey || ''}
        onChange={(e) => onSelect(e.target.value || null)}
        disabled={loading || tagKeys.length === 0}
      >
        <option value="">-- Select a Tag Key --</option>
        {tagKeys.map(tag => (
          <option key={tag.key} value={tag.key}>
            {tag.key} ({tag.sources.join(', ')}) - {tag.resourceCount} resources
          </option>
        ))}
      </select>
    </div>
  );
}

export default TagGroupSelector;
