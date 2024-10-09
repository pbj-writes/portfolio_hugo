---
date: "2024-01-07"
description: "Avoiding weight anxiety and obsession."
paige:
  file_link:
    disable: false
  style: |
    #paige-authors,
    #paige-date,
    #paige-keywords,
    #paige-reading-time,
    #paige-series,
    #paige-toc,
    .paige-authors,
    .paige-date,
    .paige-date-header,
    .paige-keywords,
    .paige-reading-time,
    .paige-series,
    .paige-summary {
        display: all;
    }
series: ["cycling"]
tags: ["zwift", "cycling", "strava"]
title: "Struggling with Zwift Weight"
---
## The struggle

<p>Just like in work, when you can automate something in life, you can eliminate some of the weirder ritualized neuroses.</p>

<p>In my case, it's about getting my weight right for each indoor ride. For whatever reason, I'm constantly obsessing about how the smallest of changes in my weight can impact my performance on a race or even just a short workout. In Zwift, it's pretty easy to manually do this, but by manually doing it before each ride, it had started to become a problem because I'd put too much mental energy into what I'm weighing. I don't do this for outdoor rides. Granted for indoor rides, you want to be fair and accurate when it comes to racing so that people aren't looking at your results skeptically, especially compared to your historical results. As a cyclist, I don't think that I'm a special case caring about the minute details of my data since the sport has a culture of shaving arms and legs, which I do not do. Although I have thought about the potential weight savings of shaving. I'm not at the aero obession phase...yet.</p>

<p>I have a Fitbit Aria smart scale that helps me address this weight obsession. Instead, I can stand on the scale each day without really even looking at the result and then step off. What happens next is automagic. My Fitbit scale updates my Zwift weight without my manual input. How does this happen? APIs, baby! Some magical person created an opt-in application that runs whenever new weight data is logged into your Fitbit account. So, you step on your scale. The scale registers the new weight data and sends it from the scale to the cloud. Once the data is in the cloud, then there's likely some POST or PUT API sending the weight data to the Zwift account.</p>

<p>Okay? So, what? Well, my Fitbit scale doesn't update my Strava profile weight. I know, I'm a lil McLooney, but, c'mon, I'm a creature of habit and consistency. If I can't control the quality of my data, then how can I trust the data? Anyway, I did a little digging. Fitbit has a robust API and Strava has a robust API, but there's just not a free application for doing what Fitbit and Zwift are doing. I did some digging. Some people are using some paid apps as a third party to update their Strava profile weight with their Fitbit scales, but I'm curious. Can't this work directly? The answer is yes.</p>

## Here's what I had to do

- set up a Fitbit developer account at [https://dev.fitbit.com](https://dev.fitbit.com/).
- register a Fitbit app at [https://dev.fitbit.com/apps/new](https://dev.fitbit.com/apps/new).
- find the API that would retrieve weight ([https://dev.fitbit.com/build/reference/web-api/body/get-weight-log](https://dev.fitbit.com/build/reference/web-api/body/get-weight-log/)).
- figure out Fitbit API authorization to get an access token; this was easy because Fitbit provides an EXTREMELY helpful authorization tutorial at [https://dev.fitbit.com/build/reference/web-api/troubleshooting-guide/oauth2-tutorial](https://dev.fitbit.com/build/reference/web-api/troubleshooting-guide/oauth2-tutorial/).
- open Postman and execute the API to retrieve weight.<br> 
{{< paige/image src="../assets/fitbit_api.png" width="75%" >}}
- register a Strava app at [https://www.strava.com/settings/api](https://www.strava.com/settings/api).
- find the API that would post weight ([https://developers.strava.com/docs/reference/#api-Athletes-updateLoggedInAthlete](https://developers.strava.com/docs/reference/#api-Athletes-updateLoggedInAthlete)).
- figure out Strava API authorization to get access token and write privileges; this was harder to figure out relative to Fitbit's guidance [https://developers.strava.com/docs/getting-started/#oauth](https://developers.strava.com/docs/getting-started/#oauth).
  - authorize my Strava app called 'Fitbit Weight Sync'.<br>
  {{< paige/image src="../assets/authorize_fitbit_weight_sync_app.png" width="20%" >}}
  - take the authorization code and retreive an access token (line 6) in Postman; notice my before weight (line 23) in the reponse below:
  {{< paige/code lang="json" options="linenos=true" >}}
{
    "token_type": "Bearer",
    "expires_at": 1704805801,
    "expires_in": 21600,
    "refresh_token": "abc123",
    "access_token": "123abc",
    "athlete": {
        "id": "me",
        "username": "pbj_",
        "resource_state": 2,
        "firstname": "P",
        "lastname": "BJ",
        "bio": null,
        "city": "Norwalk",
        "state": "California",
        "country": "United States",
        "sex": "M",
        "premium": true,
        "summit": true,
        "created_at": "2015-04-10T00:56:06Z",
        "updated_at": "2024-01-08T22:27:56Z",
        "badge_type_id": 1,
        "weight": 79.3787,
        "profile_medium": "https://dgalywyr863hv.cloudfront.net/pictures/athletes/8610265/2658905/12/medium.jpg",
        "profile": "https://dgalywyr863hv.cloudfront.net/pictures/athletes/8610265/2658905/12/large.jpg",
        "friend": null,
        "follower": null
    }
}
  {{< /paige/code >}}
- open Postman and execute the API to write the weight to my Strava profile; by the way, this is a judgement free zone; I mean really it was just the holidays, so like, ya know.<br>
{{< paige/image src="../assets/strava_api.png" width="60%" >}}

## Next steps
<p>I need to overcome a few roadblocks to move forward.</p>

- I need to understand token management. For instance, how can I renew access tokens so that the Strava and Fitbit application stays authenticated? How do I store/manage tokens as a developer pleeb? How do I do this securely?
- I need scripts to do a few things:
  - Parse the data from Fitbit to include just the weight number.
  - Automate with some cron job to retreive Fitbit weight data each day or some time increment.
  - I'm sure there's more, but this is where I'm at currently.
