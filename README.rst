ET Phone Home
=============

This is a library which allows locally installed applications to 'phone home' -
send anonymous usage statistics back to a server. We want this for IPython,
to understand questions like what platforms users are on, and how quickly they
upgrade when we make a new release.

Ethics
------

Phoning home is often considered sneaky, malicious behaviour. But web app authors
routinely use analytics to understand their users and how they interact with
the application. We think it's OK for local applications to benefit from the
same kind of data, so long as developers follow some simple guidelines:

1. Ask the user for permission before sending any data. It should be clear what
   data will be collected, and the user should be free to say no.
2. Do not attempt to collect any personal or identifying information.

There's no way we can enforce these rules on all developers using the library,
but the code and the documentation are written to encourage responsible use,
and we will use it this way in our own applications.

ETPH does generate a random, unique user ID, so that successive data points from
the same installation can be connected. This is to avoid application developers
generating an ID from potentially significant information like a MAC address.
A separate ID is generated for each application using ETPH, so your submissions
for different applications can't be correlated.
