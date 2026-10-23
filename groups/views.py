import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import GroupForm
from .models import Group, Membership


def get_membership_or_404(user, group_id):
    """Return the user's membership in this group, or a 404 if they are not a member."""
    return get_object_or_404(
        Membership.objects.select_related('group'),
        group_id=group_id,
        user=user,
    )


@login_required
def group_list(request):
    groups = (
        Group.objects
        .annotate(member_count=Count('memberships'))
        .filter(memberships__user=request.user)
        .order_by('-created_at')
    )
    return render(request, 'groups/group_list.html', {'groups': groups})


@login_required
def group_create(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                group = form.save(commit=False)
                group.created_by = request.user
                group.save()
                Membership.objects.create(
                    user=request.user,
                    group=group,
                    role=Membership.Role.ADMIN,
                )
            messages.success(request, f'{group} created! Share the invite link with your friends.')
            return redirect('groups:detail', group_id=group.id)
    else:
        form = GroupForm()
    return render(request, 'groups/group_form.html', {'form': form})


@login_required
def group_detail(request, group_id):
    membership = get_membership_or_404(request.user, group_id)
    group = membership.group
    members = group.memberships.select_related('user').order_by('joined_at')
    invite_url = request.build_absolute_uri(
        reverse('groups:join', kwargs={'invite_code': group.invite_code})
    )
    return render(request, 'groups/group_detail.html', {
        'group': group,
        'members': members,
        'is_admin': membership.role == Membership.Role.ADMIN,
        'invite_url': invite_url,
    })


@login_required
def group_join(request, invite_code):
    group = get_object_or_404(Group, invite_code=invite_code)

    if Membership.objects.filter(group=group, user=request.user).exists():
        messages.info(request, f'You are already in {group}.')
        return redirect('groups:detail', group_id=group.id)

    if request.method == 'POST':
        Membership.objects.get_or_create(group=group, user=request.user)
        messages.success(request, f'You joined {group}! ☕')
        return redirect('groups:detail', group_id=group.id)

    return render(request, 'groups/group_join.html', {
        'group': group,
        'member_count': group.memberships.count(),
    })


@login_required
@require_POST
def regenerate_invite(request, group_id):
    membership = get_membership_or_404(request.user, group_id)
    if membership.role != Membership.Role.ADMIN:
        messages.error(request, 'Only the group admin can reset the invite link.')
        return redirect('groups:detail', group_id=group_id)

    group = membership.group
    group.invite_code = uuid.uuid4()
    group.save(update_fields=['invite_code'])
    messages.success(request, 'New invite link created. The old link no longer works.')
    return redirect('groups:detail', group_id=group_id)


@login_required
@require_POST
def remove_member(request, group_id, user_id):
    membership = get_membership_or_404(request.user, group_id)
    if membership.role != Membership.Role.ADMIN:
        messages.error(request, 'Only the group admin can remove members.')
        return redirect('groups:detail', group_id=group_id)

    target = get_object_or_404(Membership, group_id=group_id, user_id=user_id)
    if target.user == request.user:
        messages.error(request, 'You cannot remove yourself. Use "Leave group" instead.')
    else:
        username = target.user.username
        target.delete()
        messages.success(request, f'{username} was removed from the group.')
    return redirect('groups:detail', group_id=group_id)


@login_required
@require_POST
def leave_group(request, group_id):
    membership = get_membership_or_404(request.user, group_id)
    group = membership.group

    if membership.role == Membership.Role.ADMIN:
        other_admins = group.memberships.filter(role=Membership.Role.ADMIN).exclude(user=request.user)
        if group.memberships.count() > 1 and not other_admins.exists():
            messages.error(request, 'You are the only admin. Make someone else admin before leaving.')
            return redirect('groups:detail', group_id=group_id)

    membership.delete()
    if not group.memberships.exists():
        group.delete()
        messages.success(request, 'You left the group. It had no members left, so it was deleted.')
    else:
        messages.success(request, f'You left {group}.')
    return redirect('groups:list')