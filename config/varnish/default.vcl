vcl 4.1;

backend featureserv {
    .host = "pg-featureserv";
    .port = "9000";
}

backend tileserv {
    .host = "pg-tileserv";
    .port = "7800";
}

sub vcl_deliver {
  # Display hit/miss info
  if (obj.hits > 0) {
    set resp.http.V-Cache = "HIT";
  }
  else {
    set resp.http.V-Cache = "MISS";
  }
}

sub vcl_backend_response {
#  unset beresp.http.set-cookie;
  if (beresp.status == 200) {
    unset beresp.http.Cache-Control;
    set beresp.http.Cache-Control = "public; max-age=30";
    set beresp.ttl = 30s;
  }
  set beresp.http.Served-By = beresp.backend.name;
  set beresp.http.V-Cache-TTL = beresp.ttl;
  set beresp.http.V-Cache-Grace = beresp.grace;
}

sub vcl_recv {
# Disable any cookie when looking for pg_feature stuff
   if (req.url ~ "^/features/") {
    unset req.http.cookie;
    set req.backend_hint = featureserv;
   }
   if (req.url ~ "^/tiles/") {
    unset req.http.cookie;
    set req.backend_hint = tileserv;
   }
}