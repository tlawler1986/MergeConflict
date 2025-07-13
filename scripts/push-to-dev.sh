#!/bin/bash

# Script to automate pushing changes from personal branch to development
# Usage: ./push-to-dev.sh "commit message"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the current branch name (should be your personal branch)
CURRENT_BRANCH=$(git branch --show-current)

# Check if we're on development branch (shouldn't be coding there)
if [[ "$CURRENT_BRANCH" == "development" ]]; then
    echo -e "${RED}Error: You should be on your personal branch, not development${NC}"
    echo -e "${RED}Switch to your personal branch before running this script${NC}"
    exit 1
fi

# Check if commit message was provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a commit message${NC}"
    echo "Usage: $0 \"your commit message\""
    exit 1
fi

COMMIT_MESSAGE="$1"

echo -e "${YELLOW}Starting git workflow from branch: $CURRENT_BRANCH${NC}"
echo ""

# Step 1: Add all changes and commit
echo -e "${GREEN}Step 1: Adding all changes...${NC}"
git add -A

echo -e "${GREEN}Step 2: Creating commit...${NC}"
git commit -m "$COMMIT_MESSAGE"

# Check if commit was successful
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}No changes to commit or commit failed${NC}"
    exit 1
fi

# Step 3: Push to personal remote branch
echo -e "${GREEN}Step 3: Pushing to origin/$CURRENT_BRANCH...${NC}"
git push origin $CURRENT_BRANCH

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to push to origin/$CURRENT_BRANCH${NC}"
    exit 1
fi

# Step 4: Switch to development branch
echo -e "${GREEN}Step 4: Switching to development branch...${NC}"
git checkout development

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to switch to development branch${NC}"
    exit 1
fi

# Step 5: Pull latest development (best practice - gets any teammate updates)
echo -e "${GREEN}Step 5: Pulling latest development from origin...${NC}"
git pull origin development

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to pull latest development. Resolve conflicts manually.${NC}"
    exit 1
fi

# Step 6: Merge personal branch into development
echo -e "${GREEN}Step 6: Merging $CURRENT_BRANCH into development...${NC}"
git merge $CURRENT_BRANCH

# Check if merge was successful
if [ $? -ne 0 ]; then
    echo -e "${RED}Merge conflict detected! Please resolve conflicts manually.${NC}"
    echo -e "${RED}After resolving, commit the merge and run: git push origin development${NC}"
    echo -e "${RED}Then switch back to your branch: git checkout $CURRENT_BRANCH${NC}"
    exit 1
fi

# Step 7: Push development to origin
echo -e "${GREEN}Step 7: Pushing development to origin...${NC}"
git push origin development

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to push development to origin${NC}"
    exit 1
fi

# Step 8: Switch back to personal branch
echo -e "${GREEN}Step 8: Switching back to $CURRENT_BRANCH...${NC}"
git checkout $CURRENT_BRANCH

echo ""
echo -e "${GREEN}✅ Workflow complete!${NC}"
echo -e "${GREEN}Your changes have been pushed to both $CURRENT_BRANCH and development branches.${NC}"
echo -e "${YELLOW}Next step: Create a pull request from your fork's development to upstream${NC}"