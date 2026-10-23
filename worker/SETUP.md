# Setting up the helper (one time, about 15 minutes)

The helper is a small free program on Cloudflare. When a coach taps Share to Kings HUDL, the site sends the highlights to the helper, and the helper saves them into the games folder here.

## Part 1: Make a GitHub key

1. On GitHub, tap your profile picture, then Settings.
2. In the left list choose Developer settings.
3. Under Personal access tokens choose Fine-grained tokens, then Generate new token.
4. Token name: kings-hudl-helper. Expiration: the longest it offers.
5. Resource owner: rlahay-cloud.
6. Repository access: Only select repositories, then pick kings-hudl.
7. Permissions, then Repository permissions: set Contents to Read and write. Leave everything else off.
8. Tap Generate token and copy it right away. GitHub shows it only once.

## Part 2: Make the helper on Cloudflare

1. Make a free account at cloudflare.com.
2. In the dashboard open Workers & Pages and choose Create, then Create Worker. Name it kings-hudl-submit and deploy it.
3. Choose Edit code. Delete what is there, paste in everything from worker.js (in this folder), and Deploy.
4. Open the Worker, then Settings, then Variables and Secrets. Add these four:
   - GITHUB_TOKEN, type Secret: the key from Part 1
   - PASSCODE, type Secret: a passcode you make up and give the coaches
   - REPO, type Text: rlahay-cloud/kings-hudl
   - ALLOWED_ORIGIN, type Text: https://rlahay-cloud.github.io
5. Tap Deploy to save them.
6. Copy the Worker's web address. It looks like https://kings-hudl-submit.something.workers.dev

## Part 3: Tell the site where the helper is

Open config.json in this repo on GitHub, tap the pencil, and put the address between the quotes after submitUrl, then commit. After a minute the Share to Kings HUDL button sends to GitHub.

## If something goes wrong

- Wrong passcode: the coach retypes it in the Coach box.
- Not sent, could not save to GitHub: the key may have expired or lack permission for this repo. Make a new key and replace GITHUB_TOKEN.
- To stop everyone sending: change the PASSCODE.
