'use strict';
$(document).ready(function() {
  var currentText = '',
      longestText = '',
      onChange,
      onCursorChange,
      onSelection,
      agencyDatasource,
      agencyAdaptor,
      footerAdaptor,
      updateEmptyState,
      typeahead,
      form,
      // how long we'll give Google Analytics to record a an action
      // before just going ahead with it, in milliseconds
      gaTimeout = 500;

  //  Set up the agency data source
  agencyDatasource = new Bloodhound({
    queryTokenizer: Bloodhound.tokenizers.whitespace,
    limit: 500, // infinity
    prefetch: {
      url: '/api/agency/',
      filter: function(response) {
        return response.objects;
      }
    },
    datumTokenizer: function(d) {
      return []
        .concat(Bloodhound.tokenizers.whitespace(d.name))
        .concat(Bloodhound.tokenizers.whitespace(d.abbreviation));
    }
  });
  // always clear local storage for new requests, at least in dev
  agencyDatasource.clearPrefetchCache();
  agencyDatasource.initialize();

  //  Set up the agency adaptor
  agencyAdaptor = {
    name: 'agencies',
    displayKey: 'value',
    source: agencyDatasource.ttAdapter(),
    templates: {
      suggestion: Handlebars.compile('<p class="agency-name">{{name}}</p>')
    }
  };
  //  Set up the footer link adaptor
  footerAdaptor = {
    name: 'footer',
    source: function(query, callback) {
      if (query.length > 0) {
        callback([{'query': query, 'isFooter': true}]);
      }
    },
    templates: {
      suggestion: Handlebars.compile('<p class="search-prompt"><strong class="return">&#9166;</strong> Search for "{{query}}" in keywords and descriptions</p>')
    }
  };

  //  Track the text as the user types
  onChange = function(ev) {
    currentText = typeahead.val();
    if (currentText.length > longestText.length) {
      longestText = currentText;
    } else if (currentText.length === 0 && longestText.length > 0) {
      //  blanked out the text after initially typing something
      ga('send', 'event', 'contacts', 'did-not-want', longestText);
      longestText = '';
    }
    form.toggleClass('tt-filled', currentText.length > 0);
  };

  //  If an agency was selected, notify analytics and redirect
  //  If the footer was selected, submit the form to redirect
  onSelection = function(ev, suggestion) {
    if (suggestion.isFooter) {
      // typeahead.val(suggestion.query);
      form.submit();
    } else {
      var callback = function() {
            clearTimeout(timeout);
            window.location = '/contacts/' + suggestion.slug + '/';
          },
          timeout = setTimeout(callback, gaTimeout);
      ga('send', 'event', 'contacts', 'select-' + suggestion.slug,
         currentText, {'hitCallback': callback});
    }
  };

  onCursorChange = function() {
    var first = form.find('.tt-dataset-agencies .tt-suggestion:first-child');
    form.find('.tt-dropdown-menu')
      .toggleClass('tt-cursor-first', first.hasClass('tt-cursor'));
  };

  //  Initialize typeahead
  typeahead = $('.scrollable-dropdown-menu .typeahead')
    .typeahead({
      hint: false,
      highlight: true,
      minLength: 1
    }, agencyAdaptor, footerAdaptor)
    .on('keyup', onChange)
    .on('typeahead:cursorchanged', onCursorChange)
    .on('typeahead:selected', onSelection);

  form = typeahead.closest('form');

  // when the clear button is clicked, clear the input and
  // trigger the change handler to toggle the tt-filled class
  form.select('.clear')
    .on('click', function() {
      typeahead
        .typeahead('val', '')
        .focus();
      onChange();
    });
});