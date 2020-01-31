var regionalsModule = (function() {
  return {
    setChampionsTable: function(event_id, event_name) {
      var req = new XMLHttpRequest();
      document.getElementById('regionals-spinner').style.display = 'inherit';
      document.getElementById('champions-table').innerHTML = '';
      document.getElementById('champions-table').classList.remove('fade-in');
      req.onreadystatechange = function() {
        if (req.readyState == 4) {
          document.getElementById('regionals-spinner').style.display = 'none';
          if (req.status == 200) {
            document.getElementById('regionals-evt').innerHTML = event_name;
            document.getElementById('champions-table').innerHTML = req.responseText;
            document.getElementById('champions-table').classList.add('fade-in');
          } else {
            document.getElementById('regionals-evt').innerHTML = '';
          }
        }
      };
      var uri = '/async/champions_by_region/' + event_id + '/regional/2019';
      req.open('GET', uri);
      req.send();
    },
  };
})();

eventSelectorModule.setSelectListener(regionalsModule.setChampionsTable);
eventSelectorModule.setDefaultEvt('333');
hashModule.expectOneKey('e');
